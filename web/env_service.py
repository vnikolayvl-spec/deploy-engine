"""Сервис инспекции (--show) и редактирования пресетов .env для веб-модуля Deploy Engine."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from engine_bridge import EngineBridge
from lib.env.env_generator import EnvGenerator
from lib.env.env_inspector import EnvInspector
from lib.env.env_parser import EnvParser
from lib.env.secret_masker import SecretMasker
from lib.ui.plan_executor import PlanExecutor


class EnvWebService:
    """Объединяет EnvInspector (--show), разбор формы .env и безопасное сохранение пресетов."""

    def __init__(self, bridge: EngineBridge) -> None:
        self.bridge = bridge
        self.parser = EnvParser()
        self.masker = SecretMasker()

    def inspect_env(
        self,
        pkg_key: str,
        reveal: bool = False,
        preset: bool = False,
        sandbox: bool = False,
        sandbox_os: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Возвращает развернутую таблицу .env (аналог deploy-engine config <pkg> --show)."""
        clean = self.bridge.validate_id(pkg_key, "пакет")
        eng = self.bridge.create_engine(sandbox=sandbox, sandbox_os=sandbox_os)
        report = EnvInspector(eng).inspect(clean, reveal=bool(reveal), preset=bool(preset))
        if not report:
            raise ValueError(f"Пакет '{clean}' не найден или не имеет .env конфигурации.")
        return report

    def get_env_form(
        self,
        pkg_key: str,
        reveal: bool = False,
        sandbox: bool = False,
        sandbox_os: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Возвращает структурированную форму редактирования .env пакета (шаблон + пресет + системный)."""
        clean = self.bridge.validate_id(pkg_key, "пакет")
        eng = self.bridge.create_engine(sandbox=sandbox, sandbox_os=sandbox_os)
        if not eng.registry.has(clean):
            raise ValueError(f"Пакет '{clean}' не найден в реестре.")
        pkg = eng.registry.get(clean)
        pkg_name = pkg.get("name", clean.split("/")[-1])
        env_spec = PlanExecutor.find_pkg_env_unit(eng, clean)
        if not env_spec:
            return {
                "package": pkg_name, "has_env": False, "fields": [],
                "preset_exists": False, "system_exists": False, "needs_confirmation": False,
            }

        unit_name, src_path, dest_path = env_spec
        preset_path = eng.env_manager.get_local_preset_path(pkg_name)
        preset_exists = os.path.isfile(preset_path)
        system_exists = os.path.isfile(dest_path)

        _, tmpl_lines = self.parser.parse_file(src_path)
        preset_kv, preset_lines = self.parser.parse_file(preset_path) if preset_exists else ({}, [])
        sys_kv, sys_lines = self.parser.parse_file(dest_path) if system_exists else ({}, [])
        skipped_in_preset = {it["key"] for it in preset_lines if it["type"] == "pair" and it.get("is_skipped")}
        skipped_in_sys = {it["key"] for it in sys_lines if it["type"] == "pair" and it.get("is_skipped")}

        fields: List[Dict[str, Any]] = []
        pending_comments: List[str] = []
        for item in tmpl_lines:
            if item["type"] == "raw":
                txt = str(item.get("raw", "")).strip()
                if txt.startswith("#"):
                    pending_comments.append(txt.lstrip("#").strip())
                elif not txt:
                    pending_comments.clear()
                continue

            key = item["key"]
            prompt = item.get("prompt")
            tmpl_val = item.get("value", "")
            is_secret = self.masker.is_sensitive(key)

            if key in skipped_in_preset or key in skipped_in_sys:
                cur_val = EnvParser.SKIP_MARKER
            elif key in preset_kv:
                cur_val = preset_kv[key]
            elif key in sys_kv:
                cur_val = sys_kv[key]
            elif prompt:
                cur_val = prompt.get("default", "")
            else:
                cur_val = tmpl_val

            is_auto = EnvParser.is_auto_value(cur_val)
            is_gen = EnvGenerator.is_gen_marker(cur_val)
            is_skip = EnvGenerator.is_skip_value(cur_val)
            masked_val = (
                self.masker.mask_value(key, cur_val)
                if (is_secret and not reveal and cur_val and not is_auto and not is_gen and not is_skip)
                else cur_val
            )
            fields.append({
                "key": key,
                "value": cur_val if reveal or not is_secret or is_auto or is_gen or is_skip else "",
                "masked_preview": masked_val,
                "has_existing_value": bool(cur_val),
                "default": (prompt.get("default", "") if prompt else tmpl_val),
                "prompt_label": (prompt.get("label", "") if prompt else ""),
                "required": bool(prompt and not prompt.get("default")),
                "comment": item.get("inline_comment") or " ".join(pending_comments),
                "is_auto": is_auto,
                "is_gen": is_gen,
                "is_skip": is_skip,
                "is_secret": is_secret,
            })
            pending_comments.clear()

        return {
            "package": pkg_name,
            "unit": unit_name,
            "has_env": True,
            "preset_path": preset_path,
            "system_path": dest_path,
            "preset_exists": preset_exists,
            "system_exists": system_exists,
            "needs_confirmation": eng.env_manager.needs_env_confirmation(pkg_name, src_path),
            "fields": fields,
        }

    def save_env_preset(
        self,
        pkg_key: str,
        values: Dict[str, Any],
        apply_system: bool = False,
        sandbox: bool = False,
        sandbox_os: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Валидирует и сохраняет пресет .env (0600, сохраняя комментарии); опционально применяет в системный .env."""
        clean = self.bridge.validate_id(pkg_key, "пакет")
        if not isinstance(values, dict):
            raise ValueError("Поле values должно быть объектом ключ-значение.")
        eng = self.bridge.create_engine(sandbox=sandbox, sandbox_os=sandbox_os)
        if not eng.registry.has(clean):
            raise ValueError(f"Пакет '{clean}' не найден в реестре.")
        pkg = eng.registry.get(clean)
        pkg_name = pkg.get("name", clean.split("/")[-1])
        env_spec = PlanExecutor.find_pkg_env_unit(eng, clean)
        if not env_spec:
            raise ValueError(f"У пакета '{pkg_name}' нет шаблона .env.")
        _, src_path, dest_path = env_spec

        # Сохраняем прежние секреты, если оператор оставил секретное поле пустым (без перезаписи)
        preset_path = eng.env_manager.get_local_preset_path(pkg_name)
        existing_preset, _ = self.parser.parse_file(preset_path) if os.path.isfile(preset_path) else ({}, [])
        existing_sys, _ = self.parser.parse_file(dest_path) if os.path.isfile(dest_path) else ({}, [])
        _, tmpl_lines = self.parser.parse_file(src_path)
        valid_keys = {it["key"] for it in tmpl_lines if it["type"] == "pair"}

        merged: Dict[str, str] = {}
        missing_required: List[str] = []
        for item in tmpl_lines:
            if item["type"] != "pair":
                continue
            k = item["key"]
            raw_in = values.get(k)
            val = "" if raw_in is None else str(raw_in).strip()
            if not val and self.masker.is_sensitive(k):
                val = existing_preset.get(k) or existing_sys.get(k) or ""
            prompt = item.get("prompt")
            if prompt and not prompt.get("default") and not val:
                missing_required.append(k)
            merged[k] = val

        for k, v in values.items():
            if k not in valid_keys and isinstance(k, str) and k.replace("_", "").isalnum():
                merged[k] = str(v).strip()

        if missing_required:
            raise ValueError(f"Заполните обязательные параметры (или укажите #SKIP#): {', '.join(missing_required)}")

        saved_preset = eng.env_manager.save_local_preset(pkg_name, src_path, merged)
        applied_path = ""
        if apply_system:
            eng.env_manager.upsert_env_file(src_path, dest_path, pkg_name=pkg_name)
            applied_path = dest_path

        return {
            "package": pkg_name,
            "preset_path": saved_preset,
            "applied_system": bool(apply_system),
            "system_path": applied_path,
            "needs_confirmation": eng.env_manager.needs_env_confirmation(pkg_name, src_path),
        }
