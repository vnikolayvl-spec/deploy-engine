"""
Parser and validator for Category / Subcategory manifests (category.json or category manifest.json).
"""
import json
import os
from typing import Any, Dict
from lib.core.manifest_validation_error import ManifestValidationError


class CategoryManifestParser:
    """
    Парсер и нормализатор манифестов категорий и подкатегорий.
    Отвечает за метаданные папок дерева: описание (desc), активность в TUI (active),
    порядок сортировки (order) и расширяемые атрибуты (meta).
    """

    CATEGORY_FILENAMES = {"category.json"}

    PACKAGE_INDICATOR_KEYS = {
        "packages",
        "units",
        "include",
        "sys_packages",
        "python_packages",
        "node_packages",
        "requires",
        "dependencies",
        "pre_install",
        "post_install",
        "pre_uninstall",
        "post_uninstall",
    }

    @classmethod
    def is_category_manifest(cls, raw_data: Dict[str, Any], filename: str = "manifest.json") -> bool:
        """
        Определяет, является ли JSON-объект манифестом подкатегории (а не пакета).
        """
        if os.path.basename(filename) in cls.CATEGORY_FILENAMES:
            return True

        manifest_type = str(raw_data.get("type") or raw_data.get("kind") or "").strip().lower()
        if manifest_type in ("category", "subcategory", "folder"):
            return True
        if manifest_type == "package":
            return False

        if raw_data.get("is_category") is True:
            return True

        # Если нет ни одного специфичного ключа пакета и нет поля name (либо заданы только поля категории)
        has_pkg_keys = any(k in raw_data and raw_data[k] for k in cls.PACKAGE_INDICATOR_KEYS)
        if has_pkg_keys:
            return False

        # Если есть поле name без других полей пакета и без флага active/type="category",
        # проверяем: если присутствует active/enabled/order/meta или нет name — это категория
        if "name" in raw_data and not any(k in raw_data for k in ("active", "enabled", "order", "meta", "title")):
            return False

        return True

    @staticmethod
    def parse_bool(value: Any, default: bool = True) -> bool:
        """Безопасное приведение флага активности (active / enabled) к bool."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            norm = value.strip().lower()
            if norm in ("false", "0", "no", "off", "disabled", "inactive"):
                return False
            if norm in ("true", "1", "yes", "on", "enabled", "active"):
                return True
        return default

    def parse_file(self, manifest_path: str) -> Dict[str, Any]:
        """Считывает и нормализует файл манифеста подкатегории."""
        if not os.path.exists(manifest_path):
            raise ManifestValidationError(f"Файл манифеста категории не найден: {manifest_path}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                raw_text = f.read().strip()
            data = json.loads(raw_text) if raw_text else {}
        except json.JSONDecodeError as err:
            raise ManifestValidationError(f"Ошибка синтаксиса JSON в {manifest_path}: {err}")
        except Exception as err:
            raise ManifestValidationError(f"Не удалось прочитать {manifest_path}: {err}")

        if not isinstance(data, dict):
            raise ManifestValidationError(f"Манифест категории {manifest_path} должен быть JSON-объектом")

        base_dir = os.path.dirname(os.path.abspath(manifest_path))
        return self.normalize_category(data, base_dir)

    def normalize_category(self, raw_data: Dict[str, Any], base_dir: str) -> Dict[str, Any]:
        """Нормализует данные манифеста подкатегории."""
        folder_name = os.path.basename(base_dir)
        name = str(raw_data.get("name") or folder_name).strip() or folder_name
        title = str(raw_data.get("title") or name).strip()
        desc = str(raw_data.get("desc") or raw_data.get("description") or "").strip()

        raw_active = raw_data.get("active") if "active" in raw_data else raw_data.get("enabled")
        active = self.parse_bool(raw_active, default=True)

        try:
            order = int(raw_data.get("order", 100))
        except (ValueError, TypeError):
            order = 100

        meta = raw_data.get("meta")
        if not isinstance(meta, dict):
            meta = {}

        return {
            "type": "category",
            "is_category": True,
            "is_folder_only": True,
            "is_multi_package": False,
            "name": name,
            "title": title,
            "desc": desc,
            "description": desc,
            "active": active,
            "order": order,
            "meta": dict(meta),
            "includes": list(raw_data.get("includes", [])),
            "units": {},
            "base_dir": base_dir,
        }
