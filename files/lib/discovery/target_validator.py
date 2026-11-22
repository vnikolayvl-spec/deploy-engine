"""
lib/discovery/target_validator.py: Валидация имен целевых пакетов и мягкие предупреждения с подсказками похожих имен.
"""
from typing import List, Optional, Tuple


class TargetValidator:
    """Проверяет наличие целевых пакетов в реестре и формирует предупреждения с подсказками."""

    def __init__(self, registry, context=None):
        self.registry = registry
        self.context = context

    def format_missing_warning(self, target: str) -> str:
        """Возвращает текст мягкого предупреждения о ненайденном пакете с подсказками похожих имен."""
        hints = self.registry.suggest_similar(target) if hasattr(self.registry, "suggest_similar") else []
        hint_str = f" 💡 Возможно, вы имели в виду: {', '.join(hints)}" if hints else ""
        return f"❗ Предупреждение: пакет '{target}' не найден в реестре.{hint_str}"

    def partition_targets(self, targets: List[str]) -> Tuple[List[str], List[str]]:
        """Разделяет список целей на существующие в реестре и отсутствующие."""
        valid: List[str] = []
        missing: List[str] = []
        for raw_t in targets or []:
            t = str(raw_t).strip() if raw_t else ""
            if not t:
                continue
            (valid if self.registry.has(t) else missing).append(t)
        return valid, missing

    def filter_existing(self, targets: List[str], op_label: str = "установки", logger=None) -> List[str]:
        """Фильтрует существующие цели, логирует мягкие предупреждения для отсутствующих."""
        log_fn = logger or (self.context.log if self.context else None)
        valid, missing = self.partition_targets(targets)
        for m in missing:
            if log_fn:
                log_fn(self.format_missing_warning(m))
        if not valid and missing and log_fn:
            log_fn(
                f"❗ Операция {op_label} пропущена: указанные пакеты не найдены "
                "(проверьте 'deploy-engine list' или 'deploy-engine scan')."
            )
        return valid
