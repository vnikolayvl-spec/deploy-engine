"""
Package cache manager for storing and loading packages.json index.
"""
import json
import os
import time
from typing import Any, Dict, Optional


class PackageCacheManager:
    """Управление кэшем обнаруженных пакетов и папок в JSON (packages.json)."""

    def __init__(self, cache_file_path: str = "packages.json"):
        self.cache_file_path = cache_file_path

    def has_cache(self) -> bool:
        """Проверяет существование файла кэша."""
        return os.path.exists(self.cache_file_path) and os.path.getsize(self.cache_file_path) > 0

    def load_cache(self) -> Optional[Dict[str, Any]]:
        """Загружает базу пакетов и папок из файла кэша."""
        if not self.has_cache():
            return None

        try:
            with open(self.cache_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "packages" in data:
                    return data
        except Exception:
            return None
        return None

    def save_cache(
        self,
        packages_index: Dict[str, Any],
        version: str = "2.1.0",
        folders_index: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Сохраняет метаданные и структуру пакетов и папок в packages.json атомарно."""
        payload = {
            "version": version,
            "updated_at": time.time(),
            "packages": packages_index,
            "folders": folders_index if folders_index is not None else {},
        }
        tmp_file = f"{self.cache_file_path}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, self.cache_file_path)
            return True
        except Exception as err:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            print(f"⚠️ Не удалось записать кэш пакетов {self.cache_file_path}: {err}")
            return False

    def invalidate(self) -> bool:
        """Удаляет файл кэша."""
        if os.path.exists(self.cache_file_path):
            try:
                os.remove(self.cache_file_path)
                return True
            except OSError:
                return False
        return True
