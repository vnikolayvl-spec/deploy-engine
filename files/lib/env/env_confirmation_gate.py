"""
lib/env/env_confirmation_gate.py: Обязательное подтверждение .env перед началом установки
для пакетов, у которых еще нет сохраненного пресета во внутреннем хранилище.
"""
import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

from lib.core.deploy_engine_error import DeployEngineError
from lib.env.env_config_editor import EnvConfigEditor


class EnvConfirmationGate:
    """Барьер обязательного подтверждения .env до запуска системного пакетного менеджера и установки файлов."""

    @staticmethod
    def find_package_env_unit(engine, pkg_key: str) -> Optional[Tuple[str, str, str, str]]:
        """Возвращает (canonical_name, unit_name, src_path, dest_path) для .env юнита пакета или None."""
        if not engine.registry.has(pkg_key):
            return None
        pkg = engine.registry.get(pkg_key)
        canonical_name = pkg.get("name", pkg_key.split("/")[-1])
        for u_name, u_spec in sorted((pkg.get("units") or {}).items()):
            if (u_spec or {}).get("type") == "env" or u_name.endswith(".env") or u_name == "deploy.env":
                try:
                    src_path, dest_path, _, _ = engine.get_paths_and_modes(f"{canonical_name}:{u_name}")
                    if os.path.isfile(src_path):
                        return canonical_name, u_name, src_path, dest_path
                except Exception:
                    continue
        return None

    @classmethod
    def collect_unconfirmed_packages(cls, engine, ordered_packages: List[str]) -> List[Dict[str, str]]:
        """
        Собирает список пакетов из плана установки, которым требуется обязательное подтверждение .env
        (у которых есть .env юнит и нет валидного сохраненного пресета во внутреннем хранилище).
        """
        pending: List[Dict[str, str]] = []
        seen = set()
        for pkg_key in ordered_packages:
            found = cls.find_package_env_unit(engine, pkg_key)
            if not found:
                continue
            canonical_name, unit_name, src_path, dest_path = found
            if canonical_name in seen:
                continue
            seen.add(canonical_name)
            if engine.env_manager.needs_env_confirmation(canonical_name, src_path):
                pending.append(
                    {
                        "pkg_key": pkg_key,
                        "pkg_name": canonical_name,
                        "unit_name": unit_name,
                        "src_path": src_path,
                        "dest_path": dest_path,
                    }
                )
        return pending

    @classmethod
    def collect_missing_required(
        cls,
        engine,
        ordered_packages: List[str],
    ) -> List[Tuple[str, List[Tuple[str, str]]]]:
        """
        Возвращает список (pkg_name, [(key, notice), ...]) для пакетов с незаполненными
        обязательными переменными {{PROMPT:...}} без значения по умолчанию.
        Учитывает сохраненный пресет и существующий системный .env (если не задан --clean-env).
        """
        missing: List[Tuple[str, List[Tuple[str, str]]]] = []
        seen = set()
        for pkg_key in ordered_packages:
            found = cls.find_package_env_unit(engine, pkg_key)
            if not found:
                continue
            canonical_name, _, src_path, dest_path = found
            if canonical_name in seen:
                continue
            seen.add(canonical_name)
            preset_path = engine.env_manager.get_local_preset_path(canonical_name)
            override_paths = [preset_path] if engine.context.clean_env else [preset_path, dest_path]
            entries = engine.env_manager.parser.parse_editable_entries(src_path, override_paths=override_paths)
            pkg_missing = [
                (entry["key"], str(entry.get("notice") or "").strip())
                for entry in entries
                if entry.get("required_prompt") and not str(entry.get("value", "")).strip()
            ]
            if pkg_missing:
                missing.append((canonical_name, pkg_missing))
        return missing

    @staticmethod
    def _format_missing_required_error(missing: List[Tuple[str, List[Tuple[str, str]]]]) -> str:
        """Формирует сообщение об ошибке со списком незаполненных обязательных параметров .env и подсказкой."""
        lines = [
            "Неинтерактивная установка остановлена: не заполнены обязательные параметры .env без значения по умолчанию:"
        ]
        hints: List[str] = []
        for pkg_name, keys in missing:
            key_parts = [f"{k} ({notice})" if notice else k for k, notice in keys]
            lines.append(f"  • {pkg_name}: {', '.join(key_parts)}")
            hints.append(f"deploy-engine config {pkg_name} --preset")
        lines.append("Заполните пресет перед установкой: " + " && ".join(hints))
        return "\n".join(lines)

    @staticmethod
    def _default_input(prompt: str) -> str:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            raise KeyboardInterrupt()
        return line.strip()

    @classmethod
    def _prompt_single_package_cli(
        cls,
        engine,
        item: Dict[str, str],
        input_fn: Callable[[str], str],
    ) -> bool:
        """Интерактивно показывает параметры .env, запрашивает обязательные поля и подтверждение [Y/e/n]."""
        pkg_name = item["pkg_name"]
        src_path = item["src_path"]
        dest_path = item["dest_path"]
        preset_path = engine.env_manager.get_local_preset_path(pkg_name)

        while True:
            entries = engine.env_manager.parser.parse_editable_entries(
                src_path,
                override_paths=[dest_path, preset_path],
            )
            values: Dict[str, str] = {}
            engine.context.log(
                f"\n🔐 Обязательное подтверждение .env до начала установки: {pkg_name} ({item['unit_name']})"
            )
            engine.context.log(f"   📁 Пресет будет сохранен в: {preset_path}")

            for entry in entries:
                key = entry["key"]
                val = str(entry.get("value", "")).strip()
                req = bool(entry.get("required_prompt"))
                is_auto = bool(entry.get("is_auto"))
                notice = entry.get("notice") or ""
                if req and not val:
                    while not val:
                        hint = f" ({notice})" if notice else ""
                        val = input_fn(f"   ❗ [ОБЯЗАТЕЛЬНО] {key}{hint}: ").strip()
                else:
                    tag = " [АВТО]" if is_auto else ""
                    shown = val if val else '""'
                    engine.context.log(f"   • {key}{tag} = {shown}")
                values[key] = val

            ans = input_fn("👉 Подтвердить .env и сохранить пресет? [Y — принять / e — открыть редактор / n — отмена]: ").strip().lower()
            if ans in ("n", "no", "н", "нет"):
                engine.context.log(f"❗ Установка отменена пользователем на этапе подтверждения .env пакета '{pkg_name}'.")
                return False
            if ans in ("e", "edit", "у", "р"):
                engine.env_manager.save_local_preset(pkg_name, src_path, values)
                EnvConfigEditor(engine).open_config(pkg_name, preset=True)
                continue
            engine.env_manager.save_local_preset(pkg_name, src_path, values)
            engine.context.log(f"✅ Пресет .env для '{pkg_name}' подтвержден и сохранен.")
            return True

    @classmethod
    def confirm_in_cli(
        cls,
        engine,
        ordered_packages: List[str],
        input_fn: Optional[Callable[[str], str]] = None,
    ) -> bool:
        """
        Выполняет обязательное подтверждение .env в CLI ДО запуска apt/brew и копирования файлов.
        В неинтерактивном режиме (--yes / DE_NONINTERACTIVE / non-TTY) останавливает установку с ошибкой,
        если у пакетов остались незаполненные обязательные поля {{PROMPT:...}} без значения по умолчанию.
        """
        ctx = engine.context
        if ctx.in_tui or ctx.dry_run:
            return True

        explicit_non_interactive = bool(ctx.non_interactive or os.environ.get("DE_NONINTERACTIVE"))
        non_tty = input_fn is None and not sys.stdin.isatty()
        if explicit_non_interactive or non_tty:
            missing = cls.collect_missing_required(engine, ordered_packages)
            if missing:
                raise DeployEngineError(cls._format_missing_required_error(missing))
            if non_tty and not explicit_non_interactive:
                pending = cls.collect_unconfirmed_packages(engine, ordered_packages)
                if pending:
                    names = ", ".join(p["pkg_name"] for p in pending)
                    ctx.log(
                        f"❗ Предупреждение: неинтерактивный stdin — пропуск подтверждения .env для: {names} "
                        "(для настройки пресета выполните 'deploy-engine config <пакет> --preset')."
                    )
            return True

        pending = cls.collect_unconfirmed_packages(engine, ordered_packages)
        if not pending:
            return True

        reader = input_fn or cls._default_input
        for item in pending:
            if not cls._prompt_single_package_cli(engine, item, reader):
                return False
        return True
