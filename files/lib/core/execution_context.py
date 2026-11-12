"""
Execution context holding runtime flags and state.
"""
from typing import Optional
from lib.config import DEFAULT_REMOTE_ENGINE_DIR


class ExecutionContext:
    """Контекст выполнения операции развертывания."""
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

    def log(self, message: str) -> None:
        """Печать информационных сообщений с учетом json_output."""
        if not self.json_output:
            print(message)

    def log_verbose(self, message: str) -> None:
        """Печать подробных отладочных сообщений."""
        if self.verbose and not self.json_output:
            print(f"🔍 [DEBUG] {message}")
