"""
Manifest parser and validator.
"""
import json
import os
from typing import Any, Dict
from lib.core.manifest_validation_error import ManifestValidationError


class ManifestParser:
    """Парсер и валидатор файлов манифеста пакетов (manifest.json)."""

    def parse_file(self, manifest_path: str) -> Dict[str, Any]:
        """Считывает и парсит JSON-файл манифеста. Пустой файл или пустой JSON валиден."""
        if not os.path.exists(manifest_path):
            raise ManifestValidationError(f"Файл манифеста не найден: {manifest_path}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    data = {}
                else:
                    data = json.loads(content)
        except json.JSONDecodeError as err:
            # Пустой файл считается валидным пустым манифестом
            if not content:
                data = {}
            else:
                raise ManifestValidationError(f"Ошибка синтаксиса JSON в {manifest_path}: {err}")
        except Exception as err:
            raise ManifestValidationError(f"Не удалось прочитать {manifest_path}: {err}")

        if not isinstance(data, dict):
            raise ManifestValidationError(f"Манифест {manifest_path} должен быть JSON объектом")

        base_dir = os.path.dirname(os.path.abspath(manifest_path))
        return self.normalize_manifest(data, base_dir)

    def normalize_manifest(self, raw_data: Dict[str, Any], base_dir: str) -> Dict[str, Any]:
        """Нормализует манифест, заполняя дефолтные поля и проверяя типы."""
        desc = str(raw_data.get("desc") or raw_data.get("description") or "").strip()
        default_name = os.path.basename(base_dir)

        # 1. Проверяем, является ли манифест чисто описательным для папки (без пакетов и юнитов)
        has_packages_dict = "packages" in raw_data and isinstance(raw_data["packages"], dict) and bool(raw_data["packages"])
        has_units_dict = "units" in raw_data and isinstance(raw_data["units"], dict) and bool(raw_data["units"])
        has_pkg_name = "name" in raw_data and bool(str(raw_data["name"]).strip())
        has_includes = bool(raw_data.get("include") or raw_data.get("includes"))

        if not has_packages_dict and not has_units_dict and not has_pkg_name and not has_includes:
            return {
                "name": default_name,
                "version": "1.0.0",
                "desc": desc,
                "description": desc,
                "requires": [],
                "sys_packages": [],
                "python_packages": [],
                "node_packages": [],
                "units": {},
                "base_dir": base_dir,
                "is_folder_only": True,
                "is_empty": len(raw_data) == 0,
            }

        # 2. Поддержка формата legacy с корневым словарем packages: { "pkg_name": { ... } }
        if has_packages_dict:
            top_units = raw_data.get("units", {})
            normalized_multi: Dict[str, Any] = {
                "is_multi_package": True,
                "includes": raw_data.get("includes", []),
                "desc": desc,
                "packages": {},
            }
            for pkg_name, pkg_data in raw_data["packages"].items():
                pkg_data["name"] = pkg_name

                # Собираем юниты пакета из includes или top-level units
                pkg_units = dict(pkg_data.get("units", {}))
                includes = pkg_data.get("include") or pkg_data.get("includes")
                if includes and top_units:
                    for inc in includes:
                        if inc in top_units:
                            pkg_units[inc] = top_units[inc]
                elif not pkg_units and top_units:
                    pkg_units = dict(top_units)
                pkg_data["units"] = pkg_units

                # Поддержка requires из includes или dependencies
                if "requires" not in pkg_data and "dependencies" in pkg_data:
                    pkg_data["requires"] = pkg_data["dependencies"]

                normalized_multi["packages"][pkg_name] = self._normalize_single_package(pkg_data, base_dir)
            return normalized_multi

        single = self._normalize_single_package(raw_data, base_dir)
        if desc and not single.get("description"):
            single["description"] = desc
            single["desc"] = desc
        return single

    def _normalize_single_package(self, data: Dict[str, Any], base_dir: str) -> Dict[str, Any]:
        """Нормализует данные отдельного пакета."""
        default_name = os.path.basename(base_dir)
        name = str(data.get("name") or default_name).strip()
        if not name:
            raise ManifestValidationError(f"У пакета в {base_dir} отсутствует обязательное имя (name)")

        desc = str(data.get("desc") or data.get("description") or "").strip()
        normalized: Dict[str, Any] = {
            "name": name,
            "version": str(data.get("version", "1.0.0")),
            "description": desc,
            "desc": desc,
            "requires": list(data.get("requires", [])),
            "sys_packages": list(data.get("sys_packages", [])),
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
