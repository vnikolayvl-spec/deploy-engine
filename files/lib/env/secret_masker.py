"""
Secret masker for sensitive environment variables in console outputs.
"""
from typing import Dict


class SecretMasker:
    """Маскирование секретов и паролей в логах и выводе консоли."""

    SENSITIVE_KEYWORDS = [
        "PASSWORD", "PASSWD", "SECRET", "TOKEN", "KEY",
        "PRIVATE", "CREDENTIAL", "AUTH", "CERT", "SIGNATURE",
    ]

    def is_sensitive(self, key: str) -> bool:
        """Проверяет, является ли имя переменной чувствительным секретом."""
        upper_key = key.upper()
        return any(keyword in upper_key for keyword in self.SENSITIVE_KEYWORDS)

    def mask_value(self, key: str, value: str) -> str:
        """Маскирует значение, если ключ чувствительный."""
        if not self.is_sensitive(key) or not value:
            return value

        val_len = len(value)
        if val_len <= 4:
            return "****"
        if val_len <= 10:
            return f"{value[:2]}****{value[-2:]}"
        return f"{value[:3]}****{value[-3:]}"

    def mask_dict(self, env_dict: Dict[str, str]) -> Dict[str, str]:
        """Возвращает копию словаря с замаскированными секретами."""
        return {k: self.mask_value(k, v) for k, v in env_dict.items()}
