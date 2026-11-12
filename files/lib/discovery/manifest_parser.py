"""
Manifest parser and validator for package manifests, delegating category manifests to CategoryManifestParser.
"""
import json
import os
from typing import Any, Dict
from lib.core.manifest_validation_error import ManifestValidationError
from lib.discovery.category_manifest_parser import CategoryManifestParser


class ManifestParser:
    """Парсер и валидатор манифестов пакетов (с делегированием манифестов подкатегорий)."""

    def __init__(self):
        self.category_parser = CategoryManifestParser()

    def parse_file(self, manifest_path: str) -> Dict[str, Any]:
        """Считывает и парсит JSON-файл манифеста пакета или подкатегории."""
        if not os.path.exists(manifest_path):
            raise ManifestValidationError(f"Файл манифеста не найден: {manifest_path}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                raw_text = f.read().strip()
            data = json.loads(raw_text) if raw_text else {}
        except json.JSONDecodeError as err:
            raise ManifestValidationError(f"Ошибка синтаксиса JSON в {manifest_path}: {err}")
        except Exception as err:
            raise ManifestValidationError(f"Не удалось прочитать {manifest_path}: {err}")

        if not isinstance(data, dict):
            raise ManifestValidationError(f"Манифест {manifest_path} должен представлять JSON-объект")

        base_dir = os.path.dirname(os.path.abspath(manifest_path))
        filename = os.path.basename(manifest_path)

        # Если файл является манифестом подкатегории — делегируем в CategoryManifestParser
        if self.category_parser.is_category_manifest(data, filename):
            return self.category_parser.normalize_category(data, base_dir)

        return self.normalize_manifest(data, base_dir)

    def normalize_manifest(self, raw_data: Dict[str, Any], base_dir: str) -> Dict[str, Any]:
        """Нормализует манифест пакета (или мульти-пакета), заполняя дефолтные поля."""
        if self.category_parser.is_category_manifest(raw_data):
            return self.category_parser.normalize_category(raw_data, base_dir)

        folder_desc = str(raw_data.get("desc") or raw_data.get("description") or "").strip()
        raw_active = raw_data.get("active") if "active" in raw_data else raw_data.get("enabled")
        folder_active = CategoryManifestParser.parse_bool(raw_active, default=True)

        # 1. Мульти-пакетный манифест с корневым словарем packages: { "pkg_name": { ... } }
        if "packages" in raw_data and isinstance(raw_data["packages"], dict) and raw_data["packages"]:
            top_units = raw_data.get("units", {})
            all_pkg_names = set(raw_data["packages"].keys())
            normalized_multi: Dict[str, Any] = {
                "type": "package",
                "is_category": False,
                "is_multi_package": True,
                "is_folder_only": False,
                "desc": folder_desc,
                "description": folder_desc,
                "active": folder_active,
                "includes": list(raw_data.get("includes", [])),
                "packages": {},
                "base_dir": base_dir,
            }
            for pkg_name, pkg_raw in raw_data["packages"].items():
                pkg_data = dict(pkg_raw or {})
                pkg_data["name"] = pkg_name

                pkg_units = dict(pkg_data.get("units", {}))
                includes = pkg_data.get("include") or pkg_data.get("includes")
                if includes and top_units:
                    for inc in includes:
                        clean_inc = inc.split(":")[-1]
                        if inc in top_units:
                            pkg_units[inc] = dict(top_units[inc])
                        elif clean_inc in top_units:
                            pkg_units[clean_inc] = dict(top_units[clean_inc])
                elif not pkg_units and top_units and not pkg_data.get("requires") and not pkg_data.get("dependencies"):
                    pkg_units = {k: dict(v) for k, v in top_units.items()}
                pkg_data["units"] = pkg_units

                if "requires" not in pkg_data and "dependencies" in pkg_data:
                    pkg_data["requires"] = pkg_data["dependencies"]

                reqs = pkg_data.get("requires", [])
                pkg_data["is_alias"] = bool(
                    not pkg_units
                    and reqs
                    and len(all_pkg_names) > 1
                    and all(r in all_pkg_names for r in reqs)
                )

                normalized_multi["packages"][pkg_name] = self._normalize_single_package(pkg_data, base_dir)
            return normalized_multi

        # 2. Одиночный пакет в манифесте
        return self._normalize_single_package(raw_data, base_dir)

    def _normalize_single_package(self, data: Dict[str, Any], base_dir: str) -> Dict[str, Any]:
        """Нормализует данные отдельного пакета."""
        default_name = os.path.basename(base_dir)
        name = str(data.get("name") or default_name).strip()
        if not name:
            raise ManifestValidationError(f"У пакета в {base_dir} отсутствует обязательное имя (name)")

        desc = str(data.get("description") or data.get("desc") or "").strip()
        raw_active = data.get("active") if "active" in data else data.get("enabled")
        active = CategoryManifestParser.parse_bool(raw_active, default=True)

        raw_platforms = data.get("platforms") if "platforms" in data else data.get("os")
        if isinstance(raw_platforms, str):
            platforms = [p.strip().lower() for p in raw_platforms.split(",") if p.strip()]
        elif isinstance(raw_platforms, list):
            platforms = [str(p).strip().lower() for p in raw_platforms if str(p).strip()]
        else:
            platforms = []

        raw_sys_pkgs = data.get("sys_packages", [])
        if isinstance(raw_sys_pkgs, dict):
            sys_packages: Any = {str(k).lower(): list(v) for k, v in raw_sys_pkgs.items() if isinstance(v, list)}
        elif isinstance(raw_sys_pkgs, list):
            sys_packages = list(raw_sys_pkgs)
        else:
            sys_packages = []

        normalized: Dict[str, Any] = {
            "type": "package",
            "is_category": False,
            "is_folder_only": False,
            "is_multi_package": False,
            "is_alias": bool(data.get("is_alias", False)),
            "active": active,
            "platforms": platforms,
            "name": name,
            "version": str(data.get("version", "1.0.0")),
            "description": desc,
            "desc": desc,
            "requires": list(data.get("requires", [])),
            "sys_packages": sys_packages,
            "python_packages": list(data.get("python_packages", [])),
            "node_packages": list(data.get("node_packages", [])),
            "units": dict(data.get("units", {})),
            "pre_install": data.get("pre_install"),
            "post_install": data.get("post_install"),
            "pre_uninstall": data.get("pre_uninstall"),
            "post_uninstall": data.get("post_uninstall"),
            "base_dir": base_dir,
        }
        return normalized
