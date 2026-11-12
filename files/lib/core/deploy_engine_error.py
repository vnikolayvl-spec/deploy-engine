"""
Base exception for all deploy engine errors.
"""

class DeployEngineError(Exception):
    """Базовое исключение для ошибок Deploy Engine."""
    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\nДетали: {self.details}"
        return self.message
