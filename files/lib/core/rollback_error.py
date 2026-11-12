"""
Rollback failure exception.
"""
from typing import List
from lib.core.deploy_engine_error import DeployEngineError


class RollbackError(DeployEngineError):
    """Исключение при сбое отката транзакции установки."""
    def __init__(self, message: str, failed_steps: List[str] = None):
        super().__init__(message)
        self.failed_steps = failed_steps or []
