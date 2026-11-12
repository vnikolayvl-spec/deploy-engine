"""
Data unit installer for persistent dynamic data (databases, state files).
"""
import os
import shutil
from typing import Optional
from deploy_config import DATA_PREFIX, STATE_DIR
from lib.core.execution_context import ExecutionContext
from lib.installer.transaction_manager import TransactionManager


class DataUnitInstaller:
    """Безопасная установка динамических данных: никогда не перезаписывает существующие данные."""

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        transaction_manager: Optional[TransactionManager] = None,
        provider=None,
    ):
        self.context = context or ExecutionContext()
        self.transaction_manager = transaction_manager or TransactionManager()
        self.provider = provider

    def get_data_dir(self, pkg_name: str) -> str:
        """Возвращает путь к каталогу данных пакета с учетом провайдера окружения."""
        state_dir = self.provider.get_paths()["state_dir"] if self.provider else STATE_DIR
        return os.path.join(state_dir, f"{DATA_PREFIX}{pkg_name}")

    def install_data_unit(self, src_path: str, dest_path: str, mode: int = 0o600) -> bool:
        """
        Устанавливает юнит типа data.
        Если целевой файл уже существует, сохраняет его без перезаписи.
        """
        dest_dir = os.path.dirname(dest_path)

        if self.context.dry_run:
            if os.path.exists(dest_path):
                self.context.log(f"🔎 [DRY-RUN] Данные: {dest_path} уже существует, сохраняется без изменений.")
            else:
                self.context.log(f"🔎 [DRY-RUN] Создание файла данных {dest_path} из {src_path} (mode {oct(mode)})")
            return True

        # Создаем каталог данных с ограниченными правами доступа (0o700)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, mode=0o700, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)

        # Критическое правило: не перезаписывать существующие пользовательские данные/БД
        if os.path.exists(dest_path):
            self.context.log(f"💾 Данные уже существуют: {dest_path} сохранен без изменений.")
            return True

        if os.path.exists(src_path):
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, dest_path)
            os.chmod(dest_path, mode)
            self.transaction_manager.record_created_file(dest_path)
            self.context.log(f"💾 Инициализирован файл данных: {dest_path} (mode {oct(mode)})")
            return True
        else:
            # Если исходный файл не предоставлен, создаем пустой файл данных
            with open(dest_path, "a", encoding="utf-8"):
                pass
            os.chmod(dest_path, mode)
            self.transaction_manager.record_created_file(dest_path)
            self.context.log(f"💾 Создан пустой файл данных: {dest_path}")
            return True

    def remove_data(self, pkg_name: str, purge: bool = False) -> None:
        """
        Удаляет каталог данных пакета только при purge=True.
        При обычном uninstall данные сохраняются!
        """
        data_dir = self.get_data_dir(pkg_name)
        if not os.path.exists(data_dir):
            return

        if purge:
            self.context.log(f"🔥 [PURGE] Полное удаление каталога данных: {data_dir}")
            shutil.rmtree(data_dir, ignore_errors=True)
        else:
            self.context.log(f"💾 Каталог данных сохранен: {data_dir} (для удаления используйте --purge)")
