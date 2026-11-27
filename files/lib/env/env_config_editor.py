"""
lib/env/env_config_editor.py: Редактирование .env пакета дефолтным системным редактором (deploy-engine config <pkg> [--preset]).
"""
import os
import shlex
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple


class EnvConfigEditor:
    """Открывает системный .env или пресет из внутреннего хранилища в дефолтном редакторе ОС."""

    EDITOR_FALLBACKS = ("vim", "vi", "nano")

    def __init__(self, engine, runner=None):
        self.engine = engine
        self._runner = runner or subprocess.run

    @classmethod
    def resolve_editor_command(cls) -> Optional[List[str]]:
        """Определяет команду системного редактора ($VISUAL -> $EDITOR -> vim -> vi -> nano)."""
        for env_var in ("VISUAL", "EDITOR"):
            raw = (os.environ.get(env_var) or "").strip()
            if raw:
                parts = shlex.split(raw)
                if parts:
                    return parts
        for candidate in cls.EDITOR_FALLBACKS:
            found = shutil.which(candidate)
            if found:
                return [found]
        return None

    @staticmethod
    def _safe_isfile(path: str) -> Optional[bool]:
        """Возвращает True/False или None при PermissionError."""
        try:
            return os.path.isfile(path)
        except PermissionError:
            return None
        except OSError:
            return False

    def _resolve_env_paths(self, pkg_query: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Возвращает (canonical_name, src_template_path, system_dest_path, preset_path).
        При отсутствии пакета возвращает (None, None, None, None).
        """
        pkg_info = self.engine.registry.get(pkg_query) if self.engine.registry.has(pkg_query) else None
        short_name = pkg_info["name"] if pkg_info else pkg_query.split("/")[-1].strip()
        state_entry = self.engine.state_repo.get_installed_package(short_name)

        if not pkg_info and not state_entry:
            return None, None, None, None

        canonical_name = pkg_info["name"] if pkg_info else short_name
        src_path: Optional[str] = None
        dest_path: Optional[str] = None

        if pkg_info:
            for u_name, u_spec in sorted((pkg_info.get("units") or {}).items()):
                if (u_spec or {}).get("type") == "env" or u_name.endswith(".env") or u_name == "deploy.env":
                    try:
                        s_p, d_p, _, _ = self.engine.get_paths_and_modes(f"{canonical_name}:{u_name}")
                        src_path = s_p if os.path.isfile(s_p) else None
                        dest_path = d_p
                        break
                    except Exception:
                        continue

        if not dest_path and state_entry:
            for f_path in state_entry.get("files") or []:
                if str(f_path).endswith(".env"):
                    dest_path = str(f_path)
                    break

        if not dest_path:
            env_dir = self.engine.env_manager.get_env_dir(canonical_name)
            candidate = os.path.join(env_dir, f"{canonical_name}.env")
            if self._safe_isfile(candidate) in (True, None):
                dest_path = candidate

        preset_path = self.engine.env_manager.get_local_preset_path(canonical_name)
        return canonical_name, src_path, dest_path, preset_path

    def _ensure_preset_seeded(self, canonical_name: str, src_path: Optional[str], dest_path: Optional[str], preset_path: str) -> bool:
        """Создает файл пресета во внутреннем хранилище из шаблона/системного .env, не изменяя репозиторий."""
        if self._safe_isfile(preset_path) is True:
            return True
        if src_path and os.path.isfile(src_path):
            overrides = [dest_path] if (dest_path and self._safe_isfile(dest_path) is True) else []
            entries = self.engine.env_manager.parser.parse_editable_entries(src_path, override_paths=overrides)
            values = {e["key"]: str(e.get("value", "")) for e in entries}
            self.engine.env_manager.save_local_preset(canonical_name, src_path, values)
            return True
        if dest_path and self._safe_isfile(dest_path) is True:
            try:
                os.makedirs(os.path.dirname(preset_path), exist_ok=True)
                shutil.copy2(dest_path, preset_path)
                os.chmod(preset_path, 0o600)
                return True
            except PermissionError:
                return False
        return False

    def open_config(self, pkg_query: str, preset: bool = False) -> bool:
        """Открывает .env пакета в системном редакторе. Без --preset открывает системный .env, с --preset — пресет."""
        clean_q = (pkg_query or "").strip()
        canonical_name, src_path, dest_path, preset_path = self._resolve_env_paths(clean_q)
        if not canonical_name:
            self.engine.context.log(self.engine.target_validator.format_missing_warning(clean_q))
            return False

        if not src_path and not dest_path and self._safe_isfile(preset_path or "") is not True:
            self.engine.context.log(f"❗ Предупреждение: у пакета '{canonical_name}' не обнаружен файл .env.")
            return False

        if preset:
            if not preset_path or not self._ensure_preset_seeded(canonical_name, src_path, dest_path, preset_path):
                self.engine.context.log(
                    f"❗ Предупреждение: не удалось подготовить пресет для '{canonical_name}' "
                    "(шаблон .env не найден или нет прав на чтение системного файла)."
                )
                return False
            target_file = preset_path
            mode_label = "пресет (.env во внутреннем хранилище)"
        else:
            if not dest_path:
                self.engine.context.log(
                    f"❗ Предупреждение: системный .env для пакета '{canonical_name}' не найден. "
                    f"Для настройки пресета до установки используйте: deploy-engine config {canonical_name} --preset"
                )
                return False
            exists_state = self._safe_isfile(dest_path)
            if exists_state is None:
                self.engine.context.log(
                    f"❗ Предупреждение: нет прав на доступ к системному файлу '{dest_path}'. "
                    f"Запустите: sudo deploy-engine config {canonical_name} "
                    f"(или используйте '--preset' для редактирования пресета)."
                )
                return False
            if exists_state is False:
                self.engine.context.log(
                    f"❗ Предупреждение: системный файл '{dest_path}' не найден (пакет ещё не установлен). "
                    f"Для предварительной настройки используйте: deploy-engine config {canonical_name} --preset"
                )
                return False
            if not os.access(dest_path, os.R_OK | os.W_OK):
                self.engine.context.log(
                    f"❗ Предупреждение: недостаточно прав для редактирования '{dest_path}'. "
                    f"Запустите: sudo deploy-engine config {canonical_name}"
                )
                return False
            target_file = dest_path
            mode_label = "системный .env"

        editor_cmd = self.resolve_editor_command()
        if not editor_cmd:
            self.engine.context.log(
                "❗ Предупреждение: не найден системный редактор (задайте переменную окружения EDITOR или установите nano/vim)."
            )
            return False

        self.engine.context.log(f"🔧 Открытие ({mode_label}): {target_file}")
        try:
            result = self._runner(editor_cmd + [target_file])
            return getattr(result, "returncode", 0) == 0
        except PermissionError:
            self.engine.context.log(
                f"❗ Предупреждение: нет прав для запуска редактора над '{target_file}'. "
                f"Запустите с sudo: sudo deploy-engine config {canonical_name}"
            )
            return False
        except OSError as err:
            self.engine.context.log(f"❗ Предупреждение: не удалось запустить редактор '{' '.join(editor_cmd)}': {err}")
            return False
