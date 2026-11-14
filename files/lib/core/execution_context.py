"""
Execution context holding runtime flags, log listeners, and per-package install_DATE.log recording.
"""
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Callable, Iterator, List, Optional
from lib.config import DEFAULT_REMOTE_ENGINE_DIR


class ExecutionContext:
    """Контекст выполнения операции развертывания с поддержкой живой трансляции и записи install_DATE.log."""

    def __init__(
        self,
        dry_run: bool = False,
        purge: bool = False,
        clean_env: bool = False,
        verbose: bool = False,
        remote: Optional[str] = None,
        remote_dir: Optional[str] = None,
        non_interactive: bool = False,
        rescan: bool = False,
        json_output: bool = False,
        sandbox: bool = False,
        sandbox_os: Optional[str] = None,
        sandbox_dir: Optional[str] = None,
        comment: str = "",
        backup_selector: Optional[str] = None,
        list_backups: bool = False,
    ):
        self.dry_run = dry_run
        self.purge = purge
        self.clean_env = clean_env
        self.verbose = verbose
        self.remote = remote
        self.remote_dir = (remote_dir or DEFAULT_REMOTE_ENGINE_DIR).rstrip("/")
        self.non_interactive = non_interactive
        self.rescan = rescan
        self.json_output = json_output
        self.sandbox = sandbox
        self.sandbox_os = sandbox_os
        self.sandbox_dir = sandbox_dir
        self.comment = comment
        self.backup_selector = backup_selector
        self.list_backups = list_backups
        self._log_listeners: List[Callable[[str], None]] = []

    def add_log_listener(self, callback: Callable[[str], None]) -> None:
        if callback not in self._log_listeners:
            self._log_listeners.append(callback)

    def remove_log_listener(self, callback: Callable[[str], None]) -> None:
        if callback in self._log_listeners:
            self._log_listeners.remove(callback)

    def _emit_to_listeners(self, text: str) -> None:
        for cb in list(self._log_listeners):
            try:
                cb(text)
            except Exception:
                pass

    def log(self, message: str) -> None:
        """Печать информационных сообщений с учетом json_output и активных слушателей."""
        if not self.json_output:
            print(message)
        self._emit_to_listeners(str(message))

    def log_verbose(self, message: str) -> None:
        """Печать подробных отладочных сообщений."""
        formatted = f"🔍 [DEBUG] {message}"
        if self.verbose and not self.json_output:
            print(formatted)
        if self.verbose:
            self._emit_to_listeners(formatted)

    @contextmanager
    def package_operation_log(self, data_pkg_dir: str, pkg_name: str, operation: str) -> Iterator[Optional[str]]:
        """Создает датированный файл install_YYYYMMDD_HHMMSS.log в data_pkg_dir и дублирует туда весь вывод операции."""
        if self.dry_run or not data_pkg_dir:
            yield None
            return
        now = time.time()
        dt = datetime.fromtimestamp(now)
        ts_str = dt.strftime("%Y%m%d_%H%M%S")
        os.makedirs(data_pkg_dir, mode=0o755, exist_ok=True)
        fname = f"install_{ts_str}.log"
        log_path = os.path.join(data_pkg_dir, fname)
        suffix = 1
        while os.path.exists(log_path):
            fname = f"install_{ts_str}_{suffix}.log"
            log_path = os.path.join(data_pkg_dir, fname)
            suffix += 1

        header = f"=== [{dt.strftime('%Y-%m-%d %H:%M:%S')}] Пакет: {pkg_name} | Операция: {operation} ===\n"
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(header)
        except OSError:
            yield None
            return

        def _file_writer(msg: str) -> None:
            if os.path.isdir(data_pkg_dir):
                try:
                    with open(log_path, "a", encoding="utf-8") as lf:
                        lf.write(f"{msg.lstrip(chr(10))}\n")
                except OSError:
                    pass

        self.add_log_listener(_file_writer)
        try:
            yield log_path
        finally:
            self.remove_log_listener(_file_writer)
