"""
Abstract base class defining the cross-platform Environment Provider contract.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from lib.core.execution_context import ExecutionContext


class BaseEnvironmentProvider(ABC):
    """
    Базовый интерфейс провайдера окружения ОС.
    Абстрагирует пакетный менеджер, системные пути, фоновые службы, права доступа и фильтрацию по ОС.
    """

    PLATFORM_ALIASES = {
        "darwin": "macos",
        "osx": "macos",
        "mac": "macos",
        "apt-get": "apt",
    }

    def __init__(self, context: Optional[ExecutionContext] = None):
        self.context = context or ExecutionContext()
        self.os_family: str = "linux"
        self.distro_id: str = "linux"
        self.distro_like: List[str] = []
        self.is_sandbox: bool = False
        self.sandbox_dir: Optional[str] = None

    @abstractmethod
    def detect_package_manager(self) -> Optional[str]:
        """Определяет доступный системный пакетный менеджер (apt-get, dnf, apk, pacman, brew, port)."""
        pass

    @abstractmethod
    def get_paths(self) -> Dict[str, str]:
        """
        Возвращает словарь системных путей для текущего окружения:
        sys_bin, sys_systemd, env_path, state_dir, opt_dir.
        """
        pass

    @abstractmethod
    def install_sys_packages(self, packages: List[str]) -> bool:
        """Устанавливает список системных пакетов с учетом специфики текущей ОС."""
        pass

    def uses_launchd_plist(self) -> bool:
        """Возвращает True, если окружение использует launchd (.plist) вместо systemd (.service/.timer)."""
        return self.os_family == "macos"

    def get_platform_tags(self) -> List[str]:
        """Возвращает список тегов текущей платформы для проверки совместимости и выбора sys_packages."""
        tags: List[str] = [self.os_family.lower(), self.distro_id.lower()]
        if self.os_family == "macos":
            tags.extend(["darwin", "osx", "mac"])
        for like in self.distro_like:
            if like.lower() not in tags:
                tags.append(like.lower())
        pm = self.detect_package_manager()
        if pm:
            pm_clean = pm.lower()
            if pm_clean not in tags:
                tags.append(pm_clean)
            if pm_clean == "apt-get" and "apt" not in tags:
                tags.append("apt")
        return tags

    def is_package_compatible(self, pkg_or_category: Dict[str, Any]) -> bool:
        """
        Проверяет, поддерживает ли пакет или подкатегория текущую ОС/платформу.
        Если поле platforms / os не задано или пустое — пакет считается универсальным (True).
        """
        raw_platforms = pkg_or_category.get("platforms")
        if raw_platforms is None:
            raw_platforms = pkg_or_category.get("os")

        if not raw_platforms:
            return True

        if isinstance(raw_platforms, str):
            platforms = [p.strip().lower() for p in raw_platforms.split(",") if p.strip()]
        elif isinstance(raw_platforms, list):
            platforms = [str(p).strip().lower() for p in raw_platforms if str(p).strip()]
        else:
            return True

        if not platforms:
            return True

        normalized_supported = set()
        for p in platforms:
            normalized_supported.add(p)
            if p in self.PLATFORM_ALIASES:
                normalized_supported.add(self.PLATFORM_ALIASES[p])

        if normalized_supported & {"all", "any", "*", "universal"}:
            return True

        current_tags = set(self.get_platform_tags())
        return bool(normalized_supported & current_tags)

    def resolve_sys_packages(self, raw_sys_packages: Any) -> List[str]:
        """
        Разрешает спецификацию sys_packages (плоский список или словарь по ОС/менеджерам)
        в плоский список пакетов для текущего окружения.
        """
        if not raw_sys_packages:
            return []

        if isinstance(raw_sys_packages, list):
            return list(dict.fromkeys([str(p).strip() for p in raw_sys_packages if str(p).strip()]))

        if isinstance(raw_sys_packages, dict):
            collected: List[str] = []
            # 1. Универсальные пакеты
            for common_key in ("common", "default", "all", "*"):
                if common_key in raw_sys_packages and isinstance(raw_sys_packages[common_key], list):
                    collected.extend(str(p).strip() for p in raw_sys_packages[common_key] if str(p).strip())

            # 2. Пакеты под семейство ОС, дистрибутив и пакетный менеджер
            pm = (self.detect_package_manager() or "").lower()
            pm_short = "apt" if pm == "apt-get" else pm
            lookup_keys: List[str] = [self.os_family.lower()]
            if self.os_family == "macos":
                lookup_keys.extend(["darwin", "osx"])
            if self.distro_id.lower() not in lookup_keys:
                lookup_keys.append(self.distro_id.lower())
            for like in self.distro_like:
                if like.lower() not in lookup_keys:
                    lookup_keys.append(like.lower())
            for k in (pm, pm_short):
                if k and k not in lookup_keys:
                    lookup_keys.append(k)

            for key in lookup_keys:
                if key in raw_sys_packages and isinstance(raw_sys_packages[key], list):
                    collected.extend(str(p).strip() for p in raw_sys_packages[key] if str(p).strip())

            return list(dict.fromkeys(collected))

        return []

    def translate_hook_command(self, command: str, pkg_name: str = "") -> str:
        """Адаптирует команду хука под текущую ОС (по умолчанию возвращает без изменений)."""
        return command

    def get_hook_env(self) -> Dict[str, str]:
        """Возвращает переменные окружения для запуска хуков."""
        import os
        return dict(os.environ)

    def requires_root(self) -> bool:
        """Возвращает True, если для записи в системные пути провайдера требуются права root."""
        return not self.is_sandbox and self.os_family == "linux"
