"""
Инспектор развернутых значений .env пакета (deploy-engine config <pkg> --show [--json] [--reveal]).
Запрашивает фактические вычисленные значения (#AUTO#, дефолты) через `<pkg> --show-config --json`
(shell=False, с таймаутом) и сопоставляет их с сырым .env с маскированием секретов.
"""
import json
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from lib.env.env_config_editor import EnvConfigEditor
from lib.env.env_generator import EnvGenerator
from lib.env.env_parser import EnvParser
from lib.env.secret_masker import SecretMasker


class EnvInspector:
    """Просмотр развернутой конфигурации .env с актуальными подстановками #AUTO# и источниками значений."""

    PROBE_TIMEOUT_SEC = 8

    def __init__(self, engine, runner=None):
        self.engine = engine
        self._runner = runner or subprocess.run
        self.parser = EnvParser()
        self.masker = SecretMasker()
        self.editor = EnvConfigEditor(engine)

    def _find_package_cli(self, canonical_name: str) -> Optional[str]:
        """Ищет установленный исполняемый файл пакета в sys_bin или PATH."""
        paths = self.engine.provider.get_paths() if getattr(self.engine, "provider", None) else {}
        sys_bin = paths.get("sys_bin", "/usr/local/bin")
        candidates = [
            os.path.join(sys_bin, canonical_name),
            os.path.join(sys_bin, f"{canonical_name}.sh"),
        ]
        state_entry = self.engine.state_repo.get_installed_package(canonical_name)
        if state_entry:
            for fpath in state_entry.get("files") or []:
                bname = os.path.basename(str(fpath))
                if bname in (canonical_name, f"{canonical_name}.sh") and os.path.isfile(fpath):
                    candidates.insert(0, str(fpath))

        for cand in candidates:
            if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
        found_path = shutil.which(canonical_name)
        return found_path

    def _probe_runtime_config(self, canonical_name: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Вызывает `<pkg> --show-config --json` (shell=False) и возвращает распарсенный JSON."""
        cli_path = self._find_package_cli(canonical_name)
        if not cli_path:
            return None, "CLI-команда пакета не найдена в системе (показаны значения из .env)"
        try:
            res = self._runner(
                [cli_path, "--show-config", "--json"],
                capture_output=True,
                text=True,
                timeout=self.PROBE_TIMEOUT_SEC,
                check=False,
            )
            if getattr(res, "returncode", 1) != 0:
                return None, "пакет не поддерживает --show-config --json (показаны значения из .env)"
            raw_out = (getattr(res, "stdout", "") or "").strip()
            if not raw_out:
                return None, "пустой ответ от --show-config --json"
            data = json.loads(raw_out)
            if isinstance(data, dict):
                return data, None
            return None, "некорректный JSON-ответ от --show-config --json"
        except Exception as err:
            return None, f"не удалось опросить runtime-конфигурацию ({err})"

    def _inspect_self(self, reveal: bool = False) -> Dict[str, Any]:
        """Инспекция собственной конфигурации Deploy Engine."""
        import lib.config as cfg_mod

        _, src_path, dest_path, preset_path = self.editor._resolve_env_paths("deploy-engine")
        env_file = next((p for p in (dest_path, preset_path, src_path) if p and os.path.isfile(p)), "")
        raw_kv, parsed_lines = self.parser.parse_file(env_file) if env_file else ({}, [])
        live_map = {
            "DE_SYS_BIN": cfg_mod.SYS_BIN,
            "DE_SYS_SYSTEMD": cfg_mod.SYS_SYSTEMD,
            "DE_ENV_PATH": cfg_mod.ENV_PATH,
            "DE_STATE_DIR": cfg_mod.STATE_DIR,
            "DE_OPT_DIR": cfg_mod.OPT_DIR,
            "DE_BACKUP_DIR": cfg_mod.BACKUP_DIR,
            "DE_LOCAL_ENV_DIR": cfg_mod.LOCAL_ENV_DIR,
            "DE_PACKAGES_DIR": cfg_mod.PACKAGES_DIR,
            "SYS_BIN": cfg_mod.SYS_BIN,
        }
        entries: Dict[str, Dict[str, Any]] = {}
        all_keys = list(dict.fromkeys(list(raw_kv.keys()) + list(live_map.keys())))
        for key in all_keys:
            raw_val = raw_kv.get(key, "")
            res_val = str(live_map.get(key, raw_val))
            src = "auto" if EnvParser.is_auto_value(raw_val) else ("env" if key in raw_kv else "default")
            is_sec = self.masker.is_sensitive(key)
            entries[key] = {
                "raw": self.masker.mask_value(key, raw_val) if (is_sec and not reveal) else raw_val,
                "resolved": self.masker.mask_value(key, res_val) if (is_sec and not reveal) else res_val,
                "source": src,
                "secret": is_sec,
            }
        return {"package": "deploy-engine", "env_file": env_file, "runtime_probe": True, "warning": None, "entries": entries}

    def inspect(self, pkg_query: str, reveal: bool = False, preset: bool = False) -> Optional[Dict[str, Any]]:
        """Собирает развернутую конфигурацию пакета (сырой .env + вычисленные значения runtime)."""
        clean_q = (pkg_query or "").strip()
        if clean_q == "deploy-engine":
            return self._inspect_self(reveal=reveal)

        canonical, src_path, dest_path, preset_path = self.editor._resolve_env_paths(clean_q)
        if not canonical:
            return None

        env_candidates = [preset_path, dest_path, src_path] if preset else [dest_path, preset_path, src_path]
        env_file = next((p for p in env_candidates if p and self.editor._safe_isfile(p) is True), "")
        raw_kv, parsed_lines = self.parser.parse_file(env_file) if env_file else ({}, [])
        skipped_keys = {item["key"] for item in parsed_lines if item["type"] == "pair" and item.get("is_skipped")}

        runtime_data, warn = (None, "режим просмотра пресета") if preset else self._probe_runtime_config(canonical)
        runtime_entries: Dict[str, Dict[str, Any]] = {}
        if isinstance(runtime_data, dict):
            if isinstance(runtime_data.get("entries"), dict):
                runtime_entries = runtime_data["entries"]
            else:
                for rk, rv in runtime_data.items():
                    if rk in ("env_file", "ok", "package"):
                        continue
                    runtime_entries[rk] = {"resolved": "" if rv is None else str(rv), "source": "runtime"}

        all_keys = list(dict.fromkeys(list(raw_kv.keys()) + list(runtime_entries.keys())))
        entries: Dict[str, Dict[str, Any]] = {}
        for key in all_keys:
            raw_val = EnvParser.SKIP_MARKER if key in skipped_keys else raw_kv.get(key, "")
            rt = runtime_entries.get(key) or {}
            is_sec = bool(rt.get("secret")) or self.masker.is_sensitive(key)

            if "resolved" in rt and rt["resolved"] is not None:
                resolved_val = str(rt["resolved"])
                source = str(rt.get("source") or ("auto" if EnvParser.is_auto_value(raw_val) else "runtime"))
            elif key in skipped_keys or EnvGenerator.is_skip_value(raw_val):
                resolved_val = ""
                source = "skip"
            elif EnvParser.is_auto_value(raw_val):
                resolved_val = "(автоопределение в runtime)"
                source = "auto"
            elif EnvGenerator.is_gen_marker(raw_val):
                resolved_val = "(генерация при установке/запуске)"
                source = "gen"
            else:
                resolved_val = raw_val
                source = "env" if key in raw_kv else "default"

            shown_raw = self.masker.mask_value(key, raw_val) if (is_sec and not reveal and not EnvParser.is_auto_value(raw_val) and not EnvGenerator.is_gen_marker(raw_val) and not EnvGenerator.is_skip_value(raw_val)) else raw_val
            shown_res = self.masker.mask_value(key, resolved_val) if (is_sec and not reveal and not resolved_val.startswith("(")) else resolved_val
            entries[key] = {
                "raw": shown_raw,
                "resolved": shown_res,
                "source": source,
                "secret": is_sec,
            }

        return {
            "package": canonical,
            "env_file": env_file,
            "runtime_probe": runtime_data is not None,
            "warning": warn,
            "entries": entries,
        }

    def format_table(self, report: Dict[str, Any]) -> str:
        """Форматирует отчет инспекции .env в виде читаемой таблицы."""
        lines = [
            f"🔎 Конфигурация пакета: {report['package']}",
            f"📄 Файл .env: {report.get('env_file') or '(не найден)'}",
        ]
        if report.get("warning"):
            lines.append(f"💡 Примечание: {report['warning']}")
        entries = report.get("entries") or {}
        if not entries:
            lines.append("(переменные не найдены)")
            return "\n".join(lines)

        lines.append("-" * 96)
        lines.append(f"{'КЛЮЧ':<28} | {'В .ENV':<22} | {'АКТУАЛЬНОЕ ЗНАЧЕНИЕ':<28} | ИСТОЧНИК")
        lines.append("-" * 96)
        for key, item in entries.items():
            raw_s = str(item.get("raw", "")) or '""'
            res_s = str(item.get("resolved", "")) or '""'
            src_s = str(item.get("source", "env"))
            lines.append(f"{key:<28} | {raw_s[:22]:<22} | {res_s[:28]:<28} | {src_s}")
        return "\n".join(lines)
