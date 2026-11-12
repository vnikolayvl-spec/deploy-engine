"""
System package manager delegating OS-specific package installation to the active EnvironmentProvider.
"""
from typing import Any, List, Optional
from lib.core.execution_context import ExecutionContext
from lib.providers.base_provider import BaseEnvironmentProvider
from lib.providers.provider_factory import EnvironmentProviderFactory


class SystemPackageManager:
    """Агрегация, разрешение под целевую ОС и установка системных пакетов через провайдер окружения."""

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        provider: Optional[BaseEnvironmentProvider] = None,
    ):
        self.context = context or ExecutionContext()
        self.provider = provider or EnvironmentProviderFactory.create(self.context)

    def detect_manager(self) -> str:
        """Возвращает активный системный пакетный менеджер текущего провайдера."""
        return self.provider.detect_package_manager() or (
            "brew" if self.provider.os_family == "macos" else "apt-get"
        )

    def resolve_for_platform(self, raw_sys_packages: Any) -> List[str]:
        """Разрешает список или словарь sys_packages под текущую ОС и пакетный менеджер."""
        return self.provider.resolve_sys_packages(raw_sys_packages)

    def install_packages(self, packages: Any) -> bool:
        """
        Разрешает и устанавливает список системных пакетов через активный провайдер окружения.
        Поддерживает как плоский список, так и словарь sys_packages.
        """
        resolved_pkgs = (
            self.resolve_for_platform(packages)
            if isinstance(packages, dict)
            else list(dict.fromkeys([str(p).strip() for p in (packages or []) if str(p).strip()]))
        )
        if not resolved_pkgs:
            return True
        return self.provider.install_sys_packages(resolved_pkgs)
