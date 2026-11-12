"""
Dependency cycle exception.
"""
from typing import List
from lib.core.deploy_engine_error import DeployEngineError


class DependencyCycleError(DeployEngineError):
    """Исключение при обнаружении циклической зависимости между пакетами."""
    def __init__(self, cycle_path: List[str]):
        chain = " -> ".join(cycle_path)
        msg = f"Обнаружена циклическая зависимость пакетов: {chain}"
        super().__init__(msg)
        self.cycle_path = cycle_path
