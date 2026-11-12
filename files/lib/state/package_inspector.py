"""
Package inspector for querying and listing installed packages and detailed package paths/descriptions.
"""
import datetime
import json
import os
from typing import Any, Dict, List, Optional
from lib.state.state_repository import StateRepository


class PackageInspector:
    """Инспекция установленных пакетов, их описания и развернутых в системе путей."""

    def __init__(self, state_repo: Optional[StateRepository] = None, engine=None):
        self.engine = engine
        self.state_repo = state_repo or (getattr(engine, "state_repo", None) if engine else None) or StateRepository()

    @staticmethod
    def _format_date(info: Dict[str, Any]) -> str:
        installed_ts = info.get("installed_at", 0)
        if isinstance(installed_ts, (int, float)) and installed_ts > 0:
            return datetime.datetime.fromtimestamp(installed_ts).strftime("%Y-%m-%d %H:%M:%S")
        ts_str = info.get("timestamp", "")
        if isinstance(ts_str, str) and ts_str:
            return ts_str
        return "N/A"

    @staticmethod
    def _infer_file_type(filepath: str) -> str:
        if os.path.islink(filepath):
            return "symlink"
        if filepath.endswith(".plist"):
            return "plist"
        if filepath.endswith(".service"):
            return "service"
        if filepath.endswith(".timer"):
            return "timer"
        if filepath.endswith(".env") or "/de_" in filepath and "/default/" in filepath:
            return "env"
        if filepath.endswith((".sh", ".py")) or "/bin/" in filepath:
            return "script"
        if "/var/lib/" in filepath or "/state/" in filepath:
            return "data"
        return "file"

    def get_installed_list(self) -> List[Dict[str, Any]]:
        """Возвращает список установленных пакетов."""
        state = self.state_repo.get_state()
        installed_map = state.get("installed", {})
        result: List[Dict[str, Any]] = []

        for name, info in sorted(installed_map.items()):
            date_str = self._format_date(info)
            files = info.get("files", [])
            result.append({
                "package": name,
                "version": info.get("version", "unknown"),
                "namespace": info.get("namespace", name),
                "description": info.get("desc", ""),
                "installed_at": date_str,
                "timestamp": info.get("installed_at", 0),
                "files_count": len(files),
                "files": files,
            })
        return result

    def get_package_info(self, pkg_query: str) -> Optional[Dict[str, Any]]:
        """Собирает полную информацию о пакете: статус, описание, категорию и пути установки."""
        reg_pkg = None
        if self.engine and self.engine.registry.has(pkg_query):
            reg_pkg = self.engine.registry.get(pkg_query)

        state_entry = self.state_repo.get_installed_package(pkg_query)
        if not state_entry and reg_pkg:
            state_entry = (
                self.state_repo.get_installed_package(reg_pkg.get("name", ""))
                or self.state_repo.get_installed_package(reg_pkg.get("namespace", ""))
            )

        if not state_entry and not reg_pkg:
            return None

        pkg_name = (reg_pkg.get("name") if reg_pkg else None) or (
            pkg_query.split("/")[-1] if state_entry else pkg_query
        )
        namespace = (
            (reg_pkg.get("namespace") if reg_pkg else None)
            or (state_entry.get("namespace") if state_entry else None)
            or pkg_name
        )
        desc = (
            (reg_pkg.get("description") or reg_pkg.get("desc") if reg_pkg else "")
            or (state_entry.get("desc") if state_entry else "")
            or ""
        )
        version = (
            (state_entry.get("version") if state_entry else None)
            or (reg_pkg.get("version") if reg_pkg else None)
            or "1.0.0"
        )

        folder_path = (reg_pkg.get("folder_path") if reg_pkg else "") or (
            os.path.dirname(namespace) if "/" in namespace else ""
        )
        category_desc = ""
        if self.engine and getattr(self.engine, "folders", None):
            cat_info = self.engine.folders.get(folder_path) or self.engine.folders.get(".")
            if cat_info:
                category_desc = cat_info.get("desc", "")

        unit_meta_by_dest: Dict[str, Dict[str, str]] = {}
        unit_meta_by_bname: Dict[str, Dict[str, str]] = {}
        resolved_manifest_paths: List[str] = []

        if reg_pkg and self.engine:
            base_dir = reg_pkg.get("base_dir", ".")
            for u_name, u_spec in (reg_pkg.get("units") or {}).items():
                try:
                    _, dest_p, _, u_type = self.engine.path_resolver.resolve(pkg_name, u_name, u_spec, base_dir)
                    u_desc = (u_spec or {}).get("desc", "")
                    meta = {"unit": u_name, "type": u_type, "desc": u_desc}
                    unit_meta_by_dest[dest_p] = meta
                    unit_meta_by_bname[os.path.basename(dest_p)] = meta
                    if dest_p not in resolved_manifest_paths:
                        resolved_manifest_paths.append(dest_p)
                except Exception:
                    pass

        raw_files = list(dict.fromkeys(state_entry.get("files", []))) if state_entry else resolved_manifest_paths
        detailed_files: List[Dict[str, Any]] = []
        for fpath in raw_files:
            meta = unit_meta_by_dest.get(fpath) or unit_meta_by_bname.get(os.path.basename(fpath)) or {}
            detailed_files.append({
                "path": fpath,
                "type": meta.get("type") or self._infer_file_type(fpath),
                "desc": meta.get("desc", ""),
                "exists": bool(os.path.exists(fpath) or os.path.islink(fpath)),
            })

        return {
            "package": pkg_name,
            "namespace": namespace,
            "installed": state_entry is not None,
            "version": version,
            "installed_at": self._format_date(state_entry) if state_entry else "не установлен",
            "description": desc,
            "category": folder_path,
            "category_description": category_desc,
            "files_count": len(detailed_files),
            "files": detailed_files,
        }

    def format_package_info(self, pkg_query: str) -> str:
        """Форматирует детальную карточку пакета с описанием и путями установки."""
        info = self.get_package_info(pkg_query)
        if not info:
            return f"❌ Пакет '{pkg_query}' не найден среди установленных пакетов и в реестре."

        status_str = "✅ УСТАНОВЛЕН" if info["installed"] else "⚪ НЕ УСТАНОВЛЕН (показаны целевые пути)"
        lines = [
            f"📦 ПАКЕТ: {info['package']}",
            "=" * 70,
            f"Статус:          {status_str}",
            f"Версия:          {info['version']}",
            f"Дата установки:  {info['installed_at']}",
            f"Описание:        {info['description'] or 'Нет описания'}",
        ]
        if info.get("category") or info.get("category_description"):
            cat_name = info.get("category") or "корень"
            cat_desc = f" ({info['category_description']})" if info.get("category_description") else ""
            lines.append(f"Категория:       {cat_name}{cat_desc}")

        lines.append("-" * 70)
        path_title = "📂 Установленные пути" if info["installed"] else "📂 Целевые пути установки"
        lines.append(f"{path_title} ({info['files_count']}):")

        if not info["files"]:
            lines.append("  (нет развернутых файлов)")
        else:
            for f_item in info["files"]:
                mark = "✓" if f_item["exists"] else "✗"
                f_type = f"[{f_item['type']}]"
                desc_part = f" — {f_item['desc']}" if f_item.get("desc") else ""
                lines.append(f"  {mark} {f_type:<10} {f_item['path']}{desc_part}")

        return "\n".join(lines)

    def format_table(self) -> str:
        """Форматирует список в виде текстовой таблицы."""
        installed = self.get_installed_list()
        if not installed:
            return "Нет установленных пакетов (состояние пусто или не инициализировано)."

        lines = [
            f"{'ПАКЕТ':<20} | {'ВЕРСИЯ':<10} | {'ДАТА УСТАНОВКИ':<20} | {'ФАЙЛОВ':<8} | ОПИСАНИЕ",
            "-" * 90,
        ]
        for item in installed:
            desc = item.get("description", "")
            lines.append(
                f"{item['package']:<20} | {item['version']:<10} | {item['installed_at']:<20} | {item['files_count']:<8} | {desc}"
            )
        return "\n".join(lines)

    def to_json(self) -> str:
        """Возвращает список установленных пакетов в формате JSON."""
        return json.dumps(self.get_installed_list(), indent=2, ensure_ascii=False)

    def info_to_json(self, targets: List[str]) -> str:
        """Возвращает детальную информацию о запрошенных пакетах в формате JSON."""
        items = [self.get_package_info(t) for t in targets]
        valid = [i for i in items if i is not None]
        return json.dumps(valid[0] if len(targets) == 1 and valid else valid, indent=2, ensure_ascii=False)
