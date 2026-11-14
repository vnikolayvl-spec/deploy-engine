"""
File installer handling file copies, permissions, symlinks, directories, and backups.
"""
import os
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, List, Optional
from lib.config import SYS_BIN, SYS_SYSTEMD
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.installer.data_unit_installer import DataUnitInstaller
from lib.installer.transaction_manager import TransactionManager


class FileInstaller:
    """Установка и удаление файлов, директорий, скриптов, юнитов systemd и симлинков."""

    PROTECTED_SYSTEM_DIRS = {
        "/", "/bin", "/sbin", "/lib", "/lib64", "/usr", "/usr/bin", "/usr/sbin",
        "/usr/local", "/usr/local/bin", "/usr/local/sbin", "/etc", "/etc/default",
        "/etc/systemd", "/etc/systemd/system", "/var", "/var/lib", "/var/tmp",
        "/opt", "/opt/homebrew", "/opt/homebrew/bin", "/tmp", "/home", "/root",
        "/Library", "/Library/LaunchDaemons", "/Library/LaunchAgents",
    }

    def __init__(self, context: Optional[ExecutionContext] = None, transaction_manager: Optional[TransactionManager] = None, provider=None):
        self.context = context or ExecutionContext()
        self.transaction_manager = transaction_manager or TransactionManager()
        self.provider = provider
        self.data_installer = DataUnitInstaller(self.context, self.transaction_manager, provider=provider)

    @staticmethod
    def _ignore_special_files(dir_path: str, names: List[str]) -> List[str]:
        ignored: List[str] = []
        for name in names:
            try:
                st_mode = os.lstat(os.path.join(dir_path, name)).st_mode
                if stat.S_ISSOCK(st_mode) or stat.S_ISFIFO(st_mode):
                    ignored.append(name)
            except OSError:
                pass
        return ignored

    def _clean_backup_path(self, backup_path: str) -> None:
        if os.path.islink(backup_path):
            os.unlink(backup_path)
        elif os.path.isdir(backup_path):
            shutil.rmtree(backup_path, ignore_errors=True)
        elif os.path.exists(backup_path):
            os.remove(backup_path)

    @staticmethod
    def _normalize_tree_permissions(dest_dir: str) -> None:
        """Авто-права внутри files/: директориям 0755 (+rX), main.py и *.sh 0755 (+x), на macOS xattr -rc."""
        parent_pkg_dir = os.path.dirname(dest_dir)
        if os.path.basename(parent_pkg_dir).startswith("de_") and os.path.isdir(parent_pkg_dir):
            try:
                os.chmod(parent_pkg_dir, 0o755)
            except OSError:
                pass
        for root, dirs, files in os.walk(dest_dir):
            for dp in [root] + [os.path.join(root, d) for d in dirs if not os.path.islink(os.path.join(root, d))]:
                try:
                    os.chmod(dp, 0o755)
                except OSError:
                    pass
            for fname in files:
                fp = os.path.join(root, fname)
                if not os.path.islink(fp):
                    try:
                        os.chmod(fp, 0o755 if (fname == "main.py" or fname.endswith(".sh")) else (stat.S_IMODE(os.stat(fp).st_mode) | 0o644))
                    except OSError:
                        pass
        if sys.platform == "darwin" and shutil.which("xattr"):
            target_xattr = parent_pkg_dir if os.path.basename(parent_pkg_dir).startswith("de_") else dest_dir
            subprocess.run(["xattr", "-rc", target_xattr], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    def install_dir_unit(self, dest_path: str, mode: int = 0o755) -> bool:
        """Создает директорию юнита type='dir' (или из секции dirs) с регистрацией в транзакции."""
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Создание директории: {dest_path} (mode {oct(mode)})")
            return True
        if not os.path.exists(dest_path):
            os.makedirs(dest_path, mode=mode, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_path)
        try:
            os.chmod(dest_path, mode)
        except OSError:
            pass
        self.context.log_verbose(f"Создана директория: {dest_path} ({oct(mode)})")
        return True

    def apply_declarative_dirs_and_chmod(self, dirs_spec: List[Any], chmod_spec: List[Any], context_vars: Dict[str, str]) -> List[str]:
        """Обрабатывает декларативные секции 'dirs' и 'chmod' пакета из manifest.json."""
        created_dirs: List[str] = []
        sb_root = self.provider.sandbox_dir if (self.provider and self.provider.is_sandbox) else None

        def _resolve_target(raw_p: str) -> str:
            res = str(raw_p).strip()
            for marker, val in context_vars.items():
                res = res.replace(marker, val)
            if sb_root and os.path.isabs(res) and not res.startswith(sb_root):
                res = os.path.join(sb_root, res.lstrip("/"))
            return os.path.normpath(res)

        for item in dirs_spec or []:
            if isinstance(item, str) and item.strip():
                d_path, d_mode = _resolve_target(item), 0o755
            elif isinstance(item, dict) and str(item.get("path") or item.get("dest") or item.get("dir") or "").strip():
                d_path = _resolve_target(str(item.get("path") or item.get("dest") or item.get("dir")))
                raw_m = item.get("mode") if item.get("mode") is not None else item.get("chmod", "0755")
                d_mode = int(str(raw_m), 8) if isinstance(raw_m, str) else int(raw_m)
            else:
                continue
            self.install_dir_unit(d_path, d_mode)
            if d_path not in created_dirs:
                created_dirs.append(d_path)

        for item in chmod_spec or []:
            if isinstance(item, dict):
                raw_p, raw_m = (item.get("path") or item.get("dest") or item.get("target") or ""), (item.get("mode") if item.get("mode") is not None else item.get("chmod", "0755"))
            elif isinstance(item, str) and ":" in item:
                raw_m, raw_p = item.split(":", 1)
            else:
                continue
            if str(raw_p).strip():
                c_path, c_mode = _resolve_target(str(raw_p)), (int(str(raw_m), 8) if isinstance(raw_m, str) else int(raw_m))
                if self.context.dry_run:
                    self.context.log(f"🔎 [DRY-RUN] Назначение прав {oct(c_mode)}: {c_path}")
                elif os.path.exists(c_path):
                    os.chmod(c_path, c_mode)
        return created_dirs

    def install_file(self, src_path: str, dest_path: str, mode: int = 0o644, unit_type: str = "file", symlink_target: Optional[str] = None, context_vars: Optional[Dict[str, str]] = None) -> bool:
        """Устанавливает файл, директорию или симлинк с сохранением бэкапа и регистрацией в транзакции."""
        if unit_type == "dir":
            return self.install_dir_unit(dest_path, mode)
        if unit_type == "data":
            return self.data_installer.install_data_unit(src_path, dest_path, mode)
        if unit_type == "symlink":
            return self._install_symlink(dest_path, symlink_target or src_path)

        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Копирование: {src_path} -> {dest_path} (mode {oct(mode)})")
            return True

        if not os.path.exists(src_path) and not os.path.islink(src_path):
            raise DeployEngineError(f"Исходный ресурс не найден на диске: {src_path}")

        dest_dir = os.path.dirname(dest_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, mode=0o755, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)

        try:
            if os.path.isdir(src_path) and not os.path.islink(src_path):
                if os.path.exists(dest_path) or os.path.islink(dest_path):
                    backup_path = f"{dest_path}.de_bak"
                    self._clean_backup_path(backup_path)
                    shutil.move(dest_path, backup_path)
                    self.transaction_manager.record_backup(dest_path, backup_path)
                else:
                    self.transaction_manager.record_created_file(dest_path)

                shutil.copytree(
                    src_path, dest_path, symlinks=True, dirs_exist_ok=True, ignore=self._ignore_special_files
                )
                self._normalize_tree_permissions(dest_path)
                self.context.log_verbose(f"Установлена директория: {dest_path} (0o755)")
                return True

            if os.path.exists(dest_path) or os.path.islink(dest_path):
                if os.path.islink(dest_path):
                    os.unlink(dest_path)
                    self.transaction_manager.record_created_file(dest_path)
                elif os.path.isdir(dest_path):
                    backup_path = f"{dest_path}.de_bak"
                    self._clean_backup_path(backup_path)
                    shutil.move(dest_path, backup_path)
                    self.transaction_manager.record_backup(dest_path, backup_path)
                else:
                    backup_path = f"{dest_path}.de_bak"
                    self._clean_backup_path(backup_path)
                    shutil.copy2(dest_path, backup_path)
                    self.transaction_manager.record_backup(dest_path, backup_path)
            else:
                self.transaction_manager.record_created_file(dest_path)

            macros = context_vars or {"{{SYS_BIN}}": SYS_BIN, "{{SYS_SYSTEMD}}": SYS_SYSTEMD}
            try:
                with open(src_path, "r", encoding="utf-8") as f_src:
                    content = f_src.read()
                for marker, real_val in macros.items():
                    content = content.replace(marker, real_val)
                with open(dest_path, "w", encoding="utf-8") as f_dest:
                    f_dest.write(content)
            except UnicodeDecodeError:
                shutil.copy2(src_path, dest_path)

            effective_mode = 0o755 if (os.path.basename(dest_path) == "main.py" or dest_path.endswith(".sh")) else mode
            os.chmod(dest_path, effective_mode)
            self.context.log_verbose(f"Установлен файл: {dest_path} ({oct(effective_mode)})")
            return True
        except Exception as err:
            raise DeployEngineError(f"Ошибка при установке {src_path} -> {dest_path}: {err}")

    def _install_symlink(self, link_path: str, target_path: str) -> bool:
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Симлинк: {link_path} -> {target_path}")
            return True
        dest_dir = os.path.dirname(link_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)
        self._clean_backup_path(link_path)
        os.symlink(target_path, link_path)
        self.transaction_manager.record_symlink(link_path)
        self.context.log_verbose(f"Симлинк создан: {link_path} -> {target_path}")
        return True

    @classmethod
    def is_safe_to_remove(cls, dest_path: str) -> bool:
        if not dest_path or not isinstance(dest_path, str):
            return False
        raw = dest_path.strip()
        if not raw or "*" in raw or "?" in raw or not os.path.isabs(raw):
            return False
        norm = os.path.normpath(raw)
        if norm in cls.PROTECTED_SYSTEM_DIRS:
            return False
        segments = [s for s in norm.strip("/").split("/") if s and s not in (".", "..")]
        return len(segments) >= 2 and segments[-1] != "de_"

    def remove_file(self, dest_path: str) -> bool:
        if not self.is_safe_to_remove(dest_path):
            self.context.log(f"🛑 Заблокировано небезопасное удаление пути: '{dest_path}'")
            return False
        norm_path = os.path.normpath(dest_path.strip())
        if not os.path.exists(norm_path) and not os.path.islink(norm_path):
            return False
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Удаление: {norm_path}")
            return True
        try:
            if os.path.islink(norm_path):
                os.unlink(norm_path)
            elif os.path.isdir(norm_path):
                shutil.rmtree(norm_path, ignore_errors=True)
            else:
                os.remove(norm_path)
            self.context.log_verbose(f"Удален: {norm_path}")
            return True
        except Exception as err:
            self.context.log(f"⚠️ Не удалось удалить {norm_path}: {err}")
            return False

    def install_plist_content(self, plist_xml: str, dest_path: str, mode: int = 0o644) -> bool:
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Генерация launchd plist: {dest_path} (mode {oct(mode)})")
            return True
        dest_dir = os.path.dirname(dest_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)
        if os.path.exists(dest_path) or os.path.islink(dest_path):
            backup_path = f"{dest_path}.de_bak"
            self._clean_backup_path(backup_path)
            shutil.copy2(dest_path, backup_path)
            self.transaction_manager.record_backup(dest_path, backup_path)
        else:
            self.transaction_manager.record_created_file(dest_path)
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(plist_xml)
        os.chmod(dest_path, mode)
        self.context.log(f"🍏 Сгенерирован launchd plist: {dest_path}")
        return True

    def install_launchd_plists(
        self, pkg_name: str, service_units: Dict[str, tuple], timer_units: Dict[str, tuple], static_env_vars: Dict[str, str], context_vars: Dict[str, str]
    ) -> List[str]:
        from lib.providers.systemd_to_plist_converter import SystemdToPlistConverter

        installed_plists: List[str] = []
        for stem in list(dict.fromkeys(list(service_units.keys()) + list(timer_units.keys()))):
            srv_entry, tmr_entry = service_units.get(stem), timer_units.get(stem)
            unit_name, _, dest_path, mode = srv_entry or tmr_entry
            srv_text = open(srv_entry[1], "r", encoding="utf-8").read() if (srv_entry and os.path.isfile(srv_entry[1])) else ""
            tmr_text = open(tmr_entry[1], "r", encoding="utf-8").read() if (tmr_entry and os.path.isfile(tmr_entry[1])) else None
            plist_xml = SystemdToPlistConverter.convert_to_xml(
                pkg_name=pkg_name, unit_name=unit_name, service_text=srv_text, timer_text=tmr_text, env_vars=static_env_vars, context_vars=context_vars
            )
            self.install_plist_content(plist_xml, dest_path, mode)
            installed_plists.append(dest_path)
        return installed_plists
