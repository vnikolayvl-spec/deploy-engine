"""
Manifest validation exception.
"""
from lib.core.deploy_engine_error import DeployEngineError


class ManifestValidationError(DeployEngineError):
    """Исключение при ошибках валидации схемы или структуры manifest.json."""
    pass
