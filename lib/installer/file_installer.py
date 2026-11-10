"""
File installer handling file copies, permissions, symlinks, and backups.
"""
import os
import shutil
from typing import Optional
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.installer.data_unit_installer import DataUnitInstaller
from lib.installer.transaction_manager import TransactionManager


class FileInstaller:
    """Установка и удаление файлов, скриптов, юнитов systemd и симлинков."""

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        transaction_manager: Optional[TransactionManager] = None,
    ):
        self.context = context or ExecutionContext()
        self.transaction_manager = transaction_manager or TransactionManager()
        self.data_installer = DataUnitInstaller(self.context, self.transaction_manager)

    def install_file(
        self,
        src_path: str,
        dest_path: str,
        mode: int = 0o644,
        unit_type: str = "file",
        symlink_target: Optional[str] = None,
    ) -> bool:
        """
        Устанавливает файл или симлинк с сохранением бэкапа и регистрацией в транзакции.
        """
        if unit_type == "data":
            return self.data_installer.install_data_unit(src_path, dest_path, mode)

        if unit_type == "symlink":
            return self._install_symlink(dest_path, symlink_target or src_path)

        dest_dir = os.path.dirname(dest_path)

        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Копирование: {src_path} -> {dest_path} (mode {oct(mode)})")
            return True

        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)

        # Резервное копирование при перезаписи
        if os.path.exists(dest_path) and not os.path.islink(dest_path):
            backup_path = f"{dest_path}.de_bak"
            shutil.copy2(dest_path, backup_path)
            self.transaction_manager.record_backup(dest_path, backup_path)
        else:
            self.transaction_manager.record_created_file(dest_path)

        # Копирование директории или файла
        try:
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dest_path)
            os.chmod(dest_path, mode)
            self.context.log_verbose(f"Установлен: {dest_path} ({oct(mode)})")
            return True
        except Exception as err:
            raise DeployEngineError(f"Ошибка при установке файла {src_path} -> {dest_path}: {err}")

    def _install_symlink(self, link_path: str, target_path: str) -> bool:
        """Создает символическую ссылку."""
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Симлинк: {link_path} -> {target_path}")
            return True

        dest_dir = os.path.dirname(link_path)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)

        if os.path.islink(link_path) or os.path.exists(link_path):
            os.unlink(link_path)

        os.symlink(target_path, link_path)
        self.transaction_manager.record_symlink(link_path)
        self.context.log_verbose(f"Симлинк создан: {link_path} -> {target_path}")
        return True

    def remove_file(self, dest_path: str) -> bool:
        """Удаляет файл или симлинк с проверкой существования."""
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
