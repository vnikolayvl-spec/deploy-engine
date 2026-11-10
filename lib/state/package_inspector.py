"""
Package inspector for querying and listing installed packages locally or remotely.
"""
import datetime
import json
from typing import Any, Dict, List, Optional
from lib.state.state_repository import StateRepository


class PackageInspector:
    """Инспекция установленных пакетов в системе."""

    def __init__(self, state_repo: Optional[StateRepository] = None):
        self.state_repo = state_repo or StateRepository()

    def get_installed_list(self) -> List[Dict[str, Any]]:
        """Возвращает список установленных пакетов."""
        state = self.state_repo.get_state()
        installed_map = state.get("installed", {})
        result: List[Dict[str, Any]] = []

        for name, info in sorted(installed_map.items()):
            installed_ts = info.get("installed_at", 0)
            date_str = (
                datetime.datetime.fromtimestamp(installed_ts).strftime("%Y-%m-%d %H:%M:%S")
                if installed_ts
                else "N/A"
            )
            result.append({
                "package": name,
                "version": info.get("version", "unknown"),
                "namespace": info.get("namespace", name),
                "installed_at": date_str,
                "timestamp": installed_ts,
                "files_count": len(info.get("files", [])),
                "files": info.get("files", []),
            })
        return result

    def format_table(self) -> str:
        """Форматирует список в виде текстовой таблицы."""
        installed = self.get_installed_list()
        if not installed:
            return "Нет установленных пакетов (состояние пусто или не инициализировано)."

        lines = [
            f"{'ПАКЕТ':<20} | {'ВЕРСИЯ':<10} | {'ДАТА УСТАНОВКИ':<20} | {'ФАЙЛОВ':<8}",
            "-" * 66,
        ]
        for item in installed:
            lines.append(
                f"{item['package']:<20} | {item['version']:<10} | {item['installed_at']:<20} | {item['files_count']:<8}"
            )
        return "\n".join(lines)

    def to_json(self) -> str:
        """Возвращает список установленных пакетов в формате JSON."""
        return json.dumps(self.get_installed_list(), indent=2, ensure_ascii=False)
