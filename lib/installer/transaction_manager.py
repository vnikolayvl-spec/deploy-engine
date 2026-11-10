"""
Transaction manager handling atomic installation steps and LIFO rollback.
"""
import os
import shutil
from typing import Any, Dict, List
from lib.core.rollback_error import RollbackError


class TransactionManager:
    """Менеджер транзакций: запись операций установки и LIFO-откат в случае сбоя."""

    ACTION_CREATED_FILE = "created_file"
    ACTION_CREATED_DIR = "created_dir"
    ACTION_BACKUP = "backup"
    ACTION_SYMLINK = "symlink"

    def __init__(self):
        self._journal: List[Dict[str, Any]] = []

    def record_created_file(self, file_path: str) -> None:
        """Регистрирует создание нового файла."""
        self._journal.append({"action": self.ACTION_CREATED_FILE, "path": file_path})

    def record_created_dir(self, dir_path: str) -> None:
        """Регистрирует создание новой директории."""
        self._journal.append({"action": self.ACTION_CREATED_DIR, "path": dir_path})

    def record_backup(self, original_path: str, backup_path: str) -> None:
        """Регистрирует создание резервной копии перезаписываемого файла."""
        self._journal.append({
            "action": self.ACTION_BACKUP,
            "original_path": original_path,
            "backup_path": backup_path,
        })

    def record_symlink(self, link_path: str) -> None:
        """Регистрирует создание символической ссылки."""
        self._journal.append({"action": self.ACTION_SYMLINK, "path": link_path})

    def rollback(self) -> None:
        """
        Выполняет обратный откат всех зарегистрированных действий в порядке LIFO.
        """
        failed_steps: List[str] = []

        while self._journal:
            entry = self._journal.pop()
            action = entry["action"]
            try:
                if action == self.ACTION_CREATED_FILE:
                    path = entry["path"]
                    if os.path.exists(path) and not os.path.islink(path):
                        os.remove(path)

                elif action == self.ACTION_SYMLINK:
                    path = entry["path"]
                    if os.path.islink(path) or os.path.exists(path):
                        os.unlink(path)

                elif action == self.ACTION_BACKUP:
                    orig = entry["original_path"]
                    bkp = entry["backup_path"]
                    if os.path.exists(bkp):
                        shutil.move(bkp, orig)

                elif action == self.ACTION_CREATED_DIR:
                    d_path = entry["path"]
                    if os.path.exists(d_path) and os.path.isdir(d_path):
                        # Удаляем директорию, только если она пуста
                        if not os.listdir(d_path):
                            os.rmdir(d_path)

            except Exception as err:
                failed_steps.append(f"Ошибка отката действия {action} ({entry}): {err}")

        if failed_steps:
            raise RollbackError("Ошибки при выполнении отката транзакции", failed_steps)

    def commit(self) -> None:
        """Подтверждает успешную транзакцию и удаляет временные файлы бэкапов."""
        for entry in self._journal:
            if entry["action"] == self.ACTION_BACKUP:
                bkp = entry.get("backup_path")
                if bkp and os.path.exists(bkp):
                    try:
                        os.remove(bkp)
                    except OSError:
                        pass
        self._journal.clear()
