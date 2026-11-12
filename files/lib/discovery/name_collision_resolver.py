"""
Resolver for package name collisions and namespace disambiguation.
"""
from typing import Dict, List, Optional
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.name_collision_error import NameCollisionError


class NameCollisionResolver:
    """Разрешение коротких имен пакетов и пространств имен."""

    def __init__(self):
        # Отображение: short_name -> [namespace1, namespace2, ...]
        self._short_to_namespaces: Dict[str, List[str]] = {}
        # Множество всех зарегистрированных полных неймспейсов
        self._all_namespaces: set = set()

    def register_package(self, namespace: str, short_name: str) -> None:
        """Регистрирует пару неймспейс и короткое имя."""
        self._all_namespaces.add(namespace)
        if short_name not in self._short_to_namespaces:
            self._short_to_namespaces[short_name] = []
        if namespace not in self._short_to_namespaces[short_name]:
            self._short_to_namespaces[short_name].append(namespace)

    def resolve(self, query: str) -> str:
        """
        Разрешает имя пакета.
        1. Если query совпадает с полным пространством имен, возвращает его.
        2. Если query - короткое имя и уникально, возвращает соответствующий неймспейс.
        3. Если query - короткое имя, но есть коллизия, возбуждает NameCollisionError.
        4. Если не найдено, возбуждает DeployEngineError.
        """
        # Прямое совпадение с неймспейсом
        if query in self._all_namespaces:
            return query

        # Поиск по короткому имени
        if query in self._short_to_namespaces:
            candidates = self._short_to_namespaces[query]
            if len(candidates) == 1:
                return candidates[0]
            raise NameCollisionError(short_name=query, candidates=candidates)

        raise DeployEngineError(f"Пакет '{query}' не найден среди обнаруженных пакетов.")

    def get_candidates(self, short_name: str) -> List[str]:
        """Возвращает список кандидатов для короткого имени."""
        return list(self._short_to_namespaces.get(short_name, []))

    def clear(self) -> None:
        """Очищает зарегистрированные имена."""
        self._short_to_namespaces.clear()
        self._all_namespaces.clear()
