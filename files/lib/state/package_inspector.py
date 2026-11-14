"""
Package inspector for querying and listing installed packages and detailed package paths/descriptions.
"""
import datetime
import json
import os
from typing import Any, Dict, List, Optional
from lib.config import DATA_PREFIX, ENV_PREFIX
from lib.state.state_repository import StateRepository


class PackageInspector:
    """Инспекция установленных пакетов, их описания и всех развернутых в системе путей."""

    def __init__(self, state_repo: Optional[StateRepository] = None, engine=None):
        self.engine = engine
        self.state_repo = state_repo or (getattr(engine, "state_repo", None) if engine else None) or StateRepository()

    @staticmethod
    def _format_date(info: Dict[str, Any]) -> str:
        installed_ts = info.get("installed_at", 0)
        if isinstance(installed_ts, (int, float)) and installed_ts > 0:
            return datetime.datetime.fromtimestamp(installed_ts).strftime("%Y-%m-%d %H:%M:%S")
        return str(info.get("timestamp") or "N/A")

    @staticmethod
    def _infer_file_type(filepath: str) -> str:
        if os.path.islink(filepath): return "symlink"
        for ext, tp in ((".plist", "plist"), (".service", "service"), (".timer", "timer"), (".env", "env")):
            if filepath.endswith(ext): return tp
        if filepath.endswith((".sh", ".py")) or "/bin/" in filepath: return "script"
        if os.path.isdir(filepath): return "file" if os.path.basename(filepath) == "files" else "dir"
        if os.path.basename(filepath).startswith("de_") or (os.path.basename(os.path.dirname(filepath)).startswith("de_") and "." not in os.path.basename(filepath)):
            return "dir"
        return "data" if ("/var/lib/" in filepath or "/state/" in filepath) else "file"

    def get_installed_list(self) -> List[Dict[str, Any]]:
        """Возвращает список установленных пакетов."""
        installed_map = self.state_repo.get_state().get("installed", {})
        return [
            {
                "package": name, "version": info.get("version", "unknown"), "namespace": info.get("namespace", name),
                "description": info.get("desc", ""), "installed_at": self._format_date(info),
                "timestamp": info.get("installed_at", 0), "files_count": len(info.get("files", [])), "files": info.get("files", []),
            }
            for name, info in sorted(installed_map.items())
        ]

    def _collect_manifest_paths_and_meta(self, pkg_name: str, reg_pkg: Dict[str, Any]) -> tuple[List[str], Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
        """Собирает полный список всех системных путей (включая родительские папки и секцию dirs) из манифеста."""
        unit_meta_by_dest: Dict[str, Dict[str, str]] = {}
        unit_meta_by_bname: Dict[str, Dict[str, str]] = {}
        resolved_paths: List[str] = []
        if not self.engine:
            return resolved_paths, unit_meta_by_dest, unit_meta_by_bname

        base_dir = reg_pkg.get("base_dir", ".")
        paths = self.engine.provider.get_paths()
        opt_pkg_dir = os.path.join(paths.get("opt_dir", "/opt"), f"de_{pkg_name}")
        env_pkg_dir = os.path.join(paths["env_path"], f"{ENV_PREFIX}{pkg_name}")
        data_pkg_dir = os.path.join(paths["state_dir"], f"{DATA_PREFIX}{pkg_name}")
        parent_labels = {
            opt_pkg_dir: "Корневой каталог пакета в /opt",
            env_pkg_dir: "Системный каталог конфигурации (.env)",
            data_pkg_dir: "Системный каталог данных пакета",
        }
        for p_dir, p_desc in parent_labels.items():
            unit_meta_by_dest[p_dir] = {"unit": os.path.basename(p_dir), "type": "dir", "desc": p_desc}

        def _add_with_parent(dest_p: str) -> None:
            for p_dir in (opt_pkg_dir, env_pkg_dir, data_pkg_dir):
                if dest_p.startswith(p_dir + os.sep) and p_dir not in resolved_paths:
                    resolved_paths.append(p_dir)
            if dest_p not in resolved_paths:
                resolved_paths.append(dest_p)

        for u_name, u_spec in (reg_pkg.get("units") or {}).items():
            try:
                _, dest_p, _, u_type = self.engine.path_resolver.resolve(pkg_name, u_name, u_spec, base_dir)
                u_desc = (u_spec or {}).get("desc", "")
                meta = {"unit": u_name, "type": u_type, "desc": u_desc}
                unit_meta_by_dest[dest_p] = meta
                unit_meta_by_bname[os.path.basename(dest_p)] = meta
                _add_with_parent(dest_p)
            except Exception:
                pass

        context_vars = {
            "{{ROOT_DIR}}": os.path.dirname(os.path.abspath(base_dir)), "{{BASE_DIR}}": os.path.abspath(base_dir),
            "{{SYS_BIN}}": paths["sys_bin"], "{{SYS_SYSTEMD}}": paths["sys_systemd"], "{{ENV_PATH}}": paths["env_path"],
            "{{STATE_DIR}}": paths["state_dir"], "{{OPT_DIR}}": paths.get("opt_dir", "/opt"),
            "{{ENV_DIR}}": env_pkg_dir, "{{DATA_DIR}}": data_pkg_dir,
        }
        sb_root = self.engine.provider.sandbox_dir if getattr(self.engine.provider, "is_sandbox", False) else None
        for d_item in reg_pkg.get("dirs") or []:
            raw_d = d_item if isinstance(d_item, str) else (d_item.get("path") or d_item.get("dest") or "") if isinstance(d_item, dict) else ""
            if not str(raw_d).strip():
                continue
            res_d = str(raw_d).strip()
            for mk, val in context_vars.items():
                res_d = res_d.replace(mk, val)
            if sb_root and os.path.isabs(res_d) and not res_d.startswith(sb_root):
                res_d = os.path.join(sb_root, res_d.lstrip("/"))
            res_d = os.path.normpath(res_d)
            d_desc = d_item.get("desc", "Директория пакета") if isinstance(d_item, dict) else "Директория пакета"
            unit_meta_by_dest.setdefault(res_d, {"unit": os.path.basename(res_d), "type": "dir", "desc": d_desc})
            _add_with_parent(res_d)

        return resolved_paths, unit_meta_by_dest, unit_meta_by_bname

    def get_package_info(self, pkg_query: str) -> Optional[Dict[str, Any]]:
        """Собирает полную информацию о пакете: статус, описание, категорию и все созданные системные пути."""
        reg_pkg = self.engine.registry.get(pkg_query) if (self.engine and self.engine.registry.has(pkg_query)) else None
        state_entry = self.state_repo.get_installed_package(pkg_query)
        if not state_entry and reg_pkg:
            state_entry = self.state_repo.get_installed_package(reg_pkg.get("name", "")) or self.state_repo.get_installed_package(reg_pkg.get("namespace", ""))
        if not state_entry and not reg_pkg:
            return None

        pkg_name = (reg_pkg.get("name") if reg_pkg else None) or (pkg_query.split("/")[-1] if state_entry else pkg_query)
        namespace = (reg_pkg.get("namespace") if reg_pkg else None) or (state_entry.get("namespace") if state_entry else None) or pkg_name
        desc = ((reg_pkg.get("description") or reg_pkg.get("desc") if reg_pkg else "") or (state_entry.get("desc") if state_entry else "") or "")
        version = (state_entry.get("version") if state_entry else None) or (reg_pkg.get("version") if reg_pkg else None) or "1.0.0"
        folder_path = (reg_pkg.get("folder_path") if reg_pkg else "") or (os.path.dirname(namespace) if "/" in namespace else "")
        category_desc = ""
        if self.engine and getattr(self.engine, "folders", None):
            cat_info = self.engine.folders.get(folder_path) or self.engine.folders.get(".")
            if cat_info:
                category_desc = cat_info.get("desc", "")

        resolved_manifest_paths, unit_meta_by_dest, unit_meta_by_bname = (
            self._collect_manifest_paths_and_meta(pkg_name, reg_pkg) if reg_pkg else ([], {}, {})
        )

        if state_entry:
            combined_paths = list(dict.fromkeys(list(state_entry.get("files", [])) + resolved_manifest_paths))
        else:
            combined_paths = resolved_manifest_paths

        detailed_files: List[Dict[str, Any]] = []
        for fpath in combined_paths:
            meta = unit_meta_by_dest.get(fpath) or unit_meta_by_bname.get(os.path.basename(fpath)) or {}
            detailed_files.append({
                "path": fpath,
                "type": meta.get("type") or self._infer_file_type(fpath),
                "desc": meta.get("desc", ""),
                "exists": bool(os.path.exists(fpath) or os.path.islink(fpath)),
            })

        mf_path = (reg_pkg.get("manifest_path") if reg_pkg else None) or (state_entry.get("manifest_path") if state_entry else "") or ""
        return {
            "package": pkg_name, "namespace": namespace, "installed": state_entry is not None,
            "version": version, "installed_at": self._format_date(state_entry) if state_entry else "не установлен",
            "description": desc, "category": folder_path, "category_description": category_desc,
            "manifest_path": mf_path, "manifest_available": reg_pkg is not None,
            "is_external_manifest": bool(reg_pkg and reg_pkg.get("is_external_manifest")),
            "files_count": len(detailed_files), "files": detailed_files,
        }

    def format_package_info(self, pkg_query: str) -> str:
        """Форматирует детальную карточку пакета с описанием и всеми системными путями."""
        info = self.get_package_info(pkg_query)
        if not info:
            return f"❌ Пакет '{pkg_query}' не найден среди установленных пакетов и в реестре."

        if info["installed"] and not info["manifest_available"]:
            status_str = "❗ УСТАНОВЛЕН (исходный манифест удален — доступны только служба и логи)"
        elif info["installed"] and info["is_external_manifest"]:
            status_str = "📌 УСТАНОВЛЕН (подгружен из внешнего манифеста)"
        else:
            status_str = "✅ УСТАНОВЛЕН" if info["installed"] else "⚪ НЕ УСТАНОВЛЕН (показаны целевые пути)"

        lines = [
            f"📦 ПАКЕТ: {info['package']}", "=" * 70,
            f"Статус:          {status_str}", f"Версия:          {info['version']}",
            f"Дата установки:  {info['installed_at']}", f"Описание:        {info['description'] or 'Нет описания'}",
        ]
        if info.get("manifest_path"):
            lines.append(f"Манифест:        {info['manifest_path']}")
        if info.get("category") or info.get("category_description"):
            cat_name = info.get("category") or "корень"
            cat_desc = f" ({info['category_description']})" if info.get("category_description") else ""
            lines.append(f"Категория:       {cat_name}{cat_desc}")

        lines.extend(["-" * 70, f"{'📂 Установленные системные пути' if info['installed'] else '📂 Целевые системные пути установки'} ({info['files_count']}):"])
        if not info["files"]:
            lines.append("  (нет развернутых путей)")
        else:
            for f_item in info["files"]:
                desc_part = f" — {f_item['desc']}" if f_item.get("desc") else ""
                lines.append(f"  {'✓' if f_item['exists'] else '✗'} {'[' + f_item['type'] + ']':<10} {f_item['path']}{desc_part}")
        return "\n".join(lines)

    def format_table(self) -> str:
        installed = self.get_installed_list()
        if not installed:
            return "Нет установленных пакетов (состояние пусто или не инициализировано)."
        lines = [f"{'ПАКЕТ':<20} | {'ВЕРСИЯ':<10} | {'ДАТА УСТАНОВКИ':<20} | {'ПУТЕЙ':<8} | ОПИСАНИЕ", "-" * 90]
        for item in installed:
            lines.append(f"{item['package']:<20} | {item['version']:<10} | {item['installed_at']:<20} | {item['files_count']:<8} | {item.get('description', '')}")
        return "\n".join(lines)

    def to_json(self) -> str:
        return json.dumps(self.get_installed_list(), indent=2, ensure_ascii=False)

    def info_to_json(self, targets: List[str]) -> str:
        valid = [i for i in (self.get_package_info(t) for t in targets) if i is not None]
        return json.dumps(valid[0] if len(targets) == 1 and valid else valid, indent=2, ensure_ascii=False)

    def _resolve_canonical_and_data_dir(self, pkg_query: str) -> tuple[str, str]:
        reg_pkg = self.engine.registry.get(pkg_query) if (self.engine and self.engine.registry.has(pkg_query)) else None
        canonical = (reg_pkg.get("name") if reg_pkg else None) or pkg_query.split("/")[-1]
        state_dir = self.engine.provider.get_paths()["state_dir"] if (self.engine and getattr(self.engine, "provider", None)) else "/var/lib"
        return canonical, os.path.join(state_dir, f"{DATA_PREFIX}{canonical}")

    def get_latest_install_log(self, pkg_query: str) -> str:
        """Возвращает содержимое последнего по времени файла install_DATE.log из /var/lib/de_<pkg>/."""
        canonical, data_dir = self._resolve_canonical_and_data_dir(pkg_query)
        if not os.path.isdir(data_dir):
            return f"📭 Для пакета '{canonical}' еще нет сохраненных логов операций в {data_dir}."
        log_files = [
            os.path.join(data_dir, f) for f in os.listdir(data_dir)
            if f.startswith("install_") and f.endswith(".log") and os.path.isfile(os.path.join(data_dir, f))
        ]
        if not log_files:
            return f"📭 В каталоге {data_dir} не найдено файлов install_*.log."
        log_files.sort(key=lambda p: (os.path.getmtime(p), os.path.basename(p)), reverse=True)
        latest = log_files[0]
        try:
            content = open(latest, "r", encoding="utf-8", errors="replace").read().strip()
            return f"📄 Файл лога: {latest}\n" + ("-" * 70) + f"\n{content}"
        except OSError as err:
            return f"❗ Ошибка чтения {latest}: {err}"

    def get_package_service_units(self, pkg_query: str) -> List[str]:
        """Возвращает список путей развернутых или целевых служб (.service, .timer, .plist) пакета."""
        info = self.get_package_info(pkg_query)
        if not info:
            return []
        return [
            f["path"] for f in info.get("files", [])
            if f.get("type") in ("service", "timer", "plist", "unit") or str(f.get("path", "")).endswith((".service", ".timer", ".plist"))
        ]

    def get_service_logs(self, pkg_query: str) -> str:
        """Возвращает статус и последние строки логов служб пакета (systemd / launchd / Sandbox)."""
        import subprocess
        units = self.get_package_service_units(pkg_query)
        if not units:
            return f"💡 У пакета '{pkg_query}' нет служб systemd / launchd."
        is_sb = bool(self.engine and getattr(self.engine.provider, "is_sandbox", False))
        blocks: List[str] = []
        for u_path in units:
            u_name = os.path.basename(u_path)
            if is_sb:
                exists_str = "развернут на диске" if os.path.exists(u_path) else "не создан"
                preview = open(u_path, "r", encoding="utf-8", errors="replace").read().strip() if os.path.isfile(u_path) else ""
                blocks.append(f"🔒 [SANDBOX] Служба {u_name} ({u_path}) — {exists_str}\n{preview}")
            elif u_name.endswith(".plist"):
                res = subprocess.run(["launchctl", "list"], capture_output=True, text=True, check=False)
                blocks.append(f"🍏 launchd plist: {u_path}\n{(res.stdout or res.stderr or '').strip()[:1500]}")
            else:
                st = subprocess.run(["systemctl", "status", u_name, "--no-pager", "-n", "15"], capture_output=True, text=True, check=False)
                jl = subprocess.run(["journalctl", "-u", u_name, "-n", "40", "--no-pager"], capture_output=True, text=True, check=False)
                blocks.append(f"🔧 Служба: {u_name}\n{(st.stdout or st.stderr or '').strip()}\n--- journalctl ---\n{(jl.stdout or jl.stderr or '').strip()}")
        return "\n\n".join(blocks)

    def restart_package_services(self, pkg_query: str) -> str:
        """Перезапускает службы пакета (systemctl restart или launchctl unload/load) и возвращает отчет."""
        import subprocess
        units = self.get_package_service_units(pkg_query)
        if not units:
            return f"❗ У пакета '{pkg_query}' нет служб для перезапуска."
        is_sb = bool(self.engine and getattr(self.engine.provider, "is_sandbox", False))
        results: List[str] = []
        for u_path in units:
            u_name = os.path.basename(u_path)
            if is_sb:
                results.append(f"🔒 [SANDBOX] Имитация перезапуска службы: {u_name}")
            elif u_name.endswith(".plist"):
                subprocess.run(["launchctl", "unload", u_path], capture_output=True, check=False)
                r = subprocess.run(["launchctl", "load", "-w", u_path], capture_output=True, text=True, check=False)
                results.append(f"🔄 Перезапущен launchd plist {u_name}: код {r.returncode}")
            else:
                r = subprocess.run(["systemctl", "restart", u_name], capture_output=True, text=True, check=False)
                results.append(f"🔄 systemctl restart {u_name}: {'OK' if r.returncode == 0 else (r.stderr or '').strip()}")
        return "\n".join(results)

