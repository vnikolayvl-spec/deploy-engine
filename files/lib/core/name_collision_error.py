"""
Package name collision exception.
"""
from typing import List
from lib.core.deploy_engine_error import DeployEngineError


class NameCollisionError(DeployEngineError):
    """Исключение при конфликте коротких имен пакетов из разных пространств имен."""
    def __init__(self, short_name: str, candidates: List[str]):
        candidates_str = ", ".join(f"'{c}'" for c in candidates)
        msg = (
            f"Конфликт имен пакетов: обнаружено несколько пакетов с именем '{short_name}'. "
            f"Кандидаты: {candidates_str}. "
            f"Пожалуйста, укажите полное пространство имен (например: {candidates[0]})."
        )
        super().__init__(msg)
        self.short_name = short_name
        self.candidates = candidates
