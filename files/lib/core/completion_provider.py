"""
lib/core/completion_provider.py: Быстрая генерация подсказок автодополнения (Zsh / Bash) для Deploy Engine.
Формат вывода: 'элемент:описание' (по одному на строку), безопасен для Zsh _describe.
"""
from typing import Dict, List, Tuple


class CompletionProvider:
    """Формирует списки команд, доступных и установленных пакетов для автодополнения оболочки."""

    COMMAND_DESCRIPTIONS: List[Tuple[str, str]] = [
        ("install", "Установить один или несколько пакетов"),
        ("uninstall", "Удалить пакет из системы"),
        ("reinstall", "Переустановить пакет"),
        ("config", "Открыть .env пакета в системном редакторе (--preset для пресета)"),
        ("info", "Показать статус, описание и пути установки пакета"),
        ("list", "Показать таблицу всех доступных и установленных пакетов"),
        ("backup", "Создать резервную копию данных и .env пакета"),
        ("restore", "Восстановить пакет из резервной копии"),
        ("scan", "Пересканировать каталог пакетов и обновить packages.json"),
        ("tui", "Открыть интерактивный TUI-интерфейс"),
        ("help", "Показать справку по командам и флагам"),
    ]

    def __init__(self, engine):
        self.engine = engine

    @staticmethod
    def _sanitize_desc(text: str) -> str:
        """Экранирует двоеточия и переводы строк для корректного парсинга Zsh _describe."""
        cleaned = " ".join(str(text or "").splitlines()).strip()
        return cleaned.replace(":", "\\:")

    def get_commands(self) -> List[str]:
        """Возвращает список подкоманд в формате 'команда:описание'."""
        return [f"{cmd}:{self._sanitize_desc(desc)}" for cmd, desc in self.COMMAND_DESCRIPTIONS]

    def get_packages(self, include_namespaces: bool = False) -> List[str]:
        """Возвращает совместимые доступные пакеты из реестра в формате 'имя:описание'."""
        seen: Dict[str, str] = {}
        for ns, pkg in sorted((self.engine.packages or {}).items()):
            if not isinstance(pkg, dict) or pkg.get("is_alias"):
                continue
            if not self.engine.is_package_compatible(pkg):
                continue
            name = str(pkg.get("name") or ns.split("/")[-1]).strip()
            desc = self._sanitize_desc(pkg.get("desc") or f"Пакет {name}")
            if name and name not in seen:
                seen[name] = desc
            if include_namespaces and ns and ns != name and ns not in seen:
                seen[ns] = desc
        return [f"{k}:{v}" for k, v in sorted(seen.items())]

    def get_installed(self) -> List[str]:
        """Возвращает установленные пакеты из state_repo в формате 'имя:описание'."""
        state_data = self.engine.state_repo.get_state() if getattr(self.engine, "state_repo", None) else {}
        installed_map = state_data.get("installed", {}) or state_data.get("installed_packages", {}) or {}
        items: List[str] = []
        for raw_key, info in sorted(installed_map.items()):
            info_dict = info if isinstance(info, dict) else {}
            name = str(info_dict.get("name") or raw_key).strip()
            ver = str(info_dict.get("version") or "").strip()
            desc = str(info_dict.get("desc") or "").strip()
            if not desc and self.engine.registry.has(name):
                desc = str(self.engine.registry.get(name).get("desc") or "").strip()
            label = f"{desc} (v{ver})" if (desc and ver) else (desc or (f"v{ver}" if ver else "Установленный пакет"))
            if name:
                items.append(f"{name}:{self._sanitize_desc(label)}")
        return items

    def render(self, mode: str = "packages") -> str:
        """Возвращает многострочный текст автодополнения для режима commands|packages|installed."""
        clean_mode = (mode or "packages").strip().lower()
        if clean_mode == "commands":
            lines = self.get_commands()
        elif clean_mode == "installed":
            lines = self.get_installed()
        elif clean_mode == "all":
            lines = self.get_packages(include_namespaces=True)
        else:
            lines = self.get_packages(include_namespaces=False)
        return "\n".join(lines)
