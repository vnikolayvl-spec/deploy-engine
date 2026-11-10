"""
File installer handling file copies, permissions, symlinks, directories, and backups.
"""
import os
import shutil
import stat
from typing import Dict, List, Optional
from deploy_config import SYS_BIN, SYS_SYSTEMD
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.installer.data_unit_installer import DataUnitInstaller
from lib.installer.transaction_manager import TransactionManager


class FileInstaller:
    """Установка и удаление файлов, директорий, скриптов, юнитов systemd и симлинков."""

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        transaction_manager: Optional[TransactionManager] = None,
    ):
        self.context = context or ExecutionContext()
        self.transaction_manager = transaction_manager or TransactionManager()
        self.data_installer = DataUnitInstaller(self.context, self.transaction_manager)

    @staticmethod
    def _ignore_special_files(dir_path: str, names: List[str]) -> List[str]:
        """Игнорирует сокеты и FIFO-каналы при рекурсивном копировании директорий."""
        ignored: List[str] = []
        for name in names:
            full_path = os.path.join(dir_path, name)
            try:
                st_mode = os.lstat(full_path).st_mode
                if stat.S_ISSOCK(st_mode) or stat.S_ISFIFO(st_mode):
                    ignored.append(name)
            except OSError:
                pass
        return ignored

    def _clean_backup_path(self, backup_path: str) -> None:
        """Удаляет старый бэкап, если он остался на диске."""
        if os.path.islink(backup_path):
            os.unlink(backup_path)
        elif os.path.isdir(backup_path):
            shutil.rmtree(backup_path, ignore_errors=True)
        elif os.path.exists(backup_path):
            os.remove(backup_path)

    def install_file(
        self,
        src_path: str,
        dest_path: str,
        mode: int = 0o644,
        unit_type: str = "file",
        symlink_target: Optional[str] = None,
        context_vars: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Устанавливает файл, директорию или симлинк с сохранением бэкапа и регистрацией в транзакции.
        """
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
            os.makedirs(dest_dir, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)

        try:
            # 1. Если источник — директория (например, папка files/)
            if os.path.isdir(src_path) and not os.path.islink(src_path):
                if os.path.exists(dest_path) or os.path.islink(dest_path):
                    backup_path = f"{dest_path}.de_bak"
                    self._clean_backup_path(backup_path)
                    shutil.move(dest_path, backup_path)
                    self.transaction_manager.record_backup(dest_path, backup_path)
                else:
                    self.transaction_manager.record_created_file(dest_path)

                shutil.copytree(
                    src_path,
                    dest_path,
                    symlinks=True,
                    dirs_exist_ok=True,
                    ignore=self._ignore_special_files,
                )
                os.chmod(dest_path, mode)
                self.context.log_verbose(f"Установлена директория: {dest_path} ({oct(mode)})")
                return True

            # 2. Если источник — одиночный файл
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

            # Подстановка макросов в текстовых файлах с фолбэком на бинарное копирование
            macros = context_vars or {
                "{{SYS_BIN}}": SYS_BIN,
                "{{SYS_SYSTEMD}}": SYS_SYSTEMD,
            }
            try:
                with open(src_path, "r", encoding="utf-8") as f_src:
                    content = f_src.read()
                for marker, real_val in macros.items():
                    content = content.replace(marker, real_val)
                with open(dest_path, "w", encoding="utf-8") as f_dest:
                    f_dest.write(content)
            except UnicodeDecodeError:
                shutil.copy2(src_path, dest_path)

            os.chmod(dest_path, mode)
            self.context.log_verbose(f"Установлен файл: {dest_path} ({oct(mode)})")
            return True

        except Exception as err:
            raise DeployEngineError(f"Ошибка при установке {src_path} -> {dest_path}: {err}")

    def _install_symlink(self, link_path: str, target_path: str) -> bool:
        """Создает символическую ссылку."""
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Симлинк: {link_path} -> {target_path}")
            return True

        dest_dir = os.path.dirname(link_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)

        if os.path.islink(link_path):
            os.unlink(link_path)
        elif os.path.isdir(link_path):
            shutil.rmtree(link_path, ignore_errors=True)
        elif os.path.exists(link_path):
            os.remove(link_path)

        os.symlink(target_path, link_path)
        self.transaction_manager.record_symlink(link_path)
        self.context.log_verbose(f"Симлинк создан: {link_path} -> {target_path}")
        return True

    def remove_file(self, dest_path: str) -> bool:
        """Удаляет файл, директорию или симлинк с проверкой существования."""
        if not os.path.exists(dest_path) and not os.path.islink(dest_path):
            return False

        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Удаление: {dest_path}")
            return True

        try:
            if os.path.islink(dest_path):
                os.unlink(dest_path)
            elif os.path.isdir(dest_path):
                shutil.rmtree(dest_path, ignore_errors=True)
            else:
                os.remove(dest_path)
            self.context.log_verbose(f"Удален: {dest_path}")
            return True
        except Exception as err:
            self.context.log(f"⚠️ Не удалось удалить {dest_path}: {err}")
            return False
