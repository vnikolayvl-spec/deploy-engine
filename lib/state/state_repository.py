"""
State repository managing state.json across root/user paths, legacy v1 format, and filesystem verification.
"""
import json
import os
import time
from typing import Any, Dict, List, Optional
from deploy_config import ENV_PATH, ENV_PREFIX
from lib.core.execution_context import ExecutionContext


class StateRepository:
    """Хранилище состояния установленных пакетов с поддержкой кроссплатформенных путей и автодетекта."""

    def __init__(
        self,
        state_file_path: Optional[str] = None,
        context: Optional[ExecutionContext] = None,
        provider=None,
        registry=None,
        path_resolver=None,
    ):
        self.context = context or ExecutionContext()
        self.provider = provider
        self.registry = registry
        self.path_resolver = path_resolver
        self._explicit_state_file = state_file_path
        env_base = self.provider.get_paths()["env_path"] if self.provider else ENV_PATH
        self.state_file_path = state_file_path or os.path.join(env_base, "state.json")

    def bind_discovery(self, registry, path_resolver=None) -> None:
        """Привязывает реестр пакетов и резолвер путей для физической проверки установленных файлов."""
        self.registry = registry
        self.path_resolver = path_resolver

    def _is_isolated_mode(self) -> bool:
        """Возвращает True, если используется песочница или явно переданный тестовый файл состояния."""
        if self._explicit_state_file:
            return True
        if getattr(self.context, "sandbox", False):
            return True
        return bool(self.provider and getattr(self.provider, "is_sandbox", False))

    def _get_candidate_state_files(self) -> List[str]:
        """Возвращает список файлов state.json для чтения (системный /etc/default и пользовательский на macOS)."""
        if self._is_isolated_mode():
            return [self.state_file_path]

        candidates = [
            "/etc/default/state.json",
            os.path.join(ENV_PATH, "state.json"),
            os.path.join(os.path.expanduser("~"), ".config", "deploy-engine", "default", "state.json"),
        ]
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            candidates.append(
                os.path.join(os.path.expanduser(f"~{sudo_user}"), ".config", "deploy-engine", "default", "state.json")
            )
        candidates.append(self.state_file_path)

        unique: List[str] = []
        for path in candidates:
            if path and path not in unique:
                unique.append(path)
        return unique

    @staticmethod
    def _normalize_entry(pkg_key: str, raw_entry: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализует запись о пакете из формата v1 (installed_packages) или v2+ (installed)."""
        installed_at = raw_entry.get("installed_at", 0)
        ts_raw = raw_entry.get("timestamp", "")
        if not installed_at and isinstance(ts_raw, (int, float)):
            installed_at = ts_raw
        return {
            "version": str(raw_entry.get("version", "1.0.0")),
            "installed_at": installed_at,
            "timestamp": str(ts_raw) if isinstance(ts_raw, str) else "",
            "files": list(dict.fromkeys(raw_entry.get("files", []))),
            "namespace": str(raw_entry.get("namespace") or pkg_key),
            "desc": str(raw_entry.get("desc") or raw_entry.get("description") or ""),
        }

    def _read_single_state_file(self, filepath: str) -> Dict[str, Dict[str, Any]]:
        """Считывает и нормализует записи из одного файла state.json (поддерживает installed и installed_packages)."""
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            merged_raw: Dict[str, Any] = {}
            if isinstance(data.get("installed_packages"), dict):
                merged_raw.update(data["installed_packages"])
            if isinstance(data.get("installed"), dict):
                merged_raw.update(data["installed"])
            return {
                k: self._normalize_entry(k, v)
                for k, v in merged_raw.items()
                if isinstance(v, dict)
            }
        except Exception:
            return {}

    def _probe_unit_on_disk(self, pkg_name: str, u_name: str, primary_dest: str, u_type: str) -> Optional[str]:
        """Проверяет фактическое наличие развернутого файла юнита по стандартным системным и пользовательским путям."""
        bname = os.path.basename(primary_dest or u_name.split(":")[-1])
        home = os.path.expanduser("~")
        candidates = [primary_dest]

        if u_type in ("script", "symlink"):
            for bdir in ("/opt/homebrew/bin", "/usr/local/bin", os.path.join(home, ".local", "bin")):
                candidates.append(os.path.join(bdir, bname))
        elif u_type == "file":
            clean_u = u_name.split(":")[-1]
            for odir in ("/opt", os.path.join(home, ".local", "opt")):
                base_f = os.path.join(odir, f"de_{pkg_name}", "files")
                candidates.append(base_f if clean_u == "files" else os.path.join(base_f, clean_u))
        elif u_type == "env":
            for edir in ("/etc/default", os.path.join(home, ".config", "deploy-engine", "default")):
                candidates.append(os.path.join(edir, f"{ENV_PREFIX}{pkg_name}", bname))
        elif u_type in ("unit", "service", "timer"):
            for sdir in ("/etc/systemd/system", "/Library/LaunchDaemons", os.path.join(home, "Library", "LaunchAgents")):
                candidates.append(os.path.join(sdir, bname))

        for cand in candidates:
            if cand and (os.path.exists(cand) or os.path.islink(cand)):
                return cand
        return None

    def _detect_installed_from_filesystem(self, known_installed: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Обнаруживает фактически установленные в системе пакеты по их развернутым файлам (если state.json недоступен)."""
        if self._is_isolated_mode() or not self.registry or not getattr(self.registry, "packages", None):
            return {}

        detected: Dict[str, Dict[str, Any]] = {}
        for reg_key, pkg_info in self.registry.packages.items():
            if pkg_info.get("is_alias"):
                continue
            pkg_name = pkg_info.get("name", reg_key.split("/")[-1])
            if pkg_name in known_installed or reg_key in known_installed:
                continue

            units = pkg_info.get("units") or {}
            if not units:
                continue

            base_dir = pkg_info.get("base_dir", ".")
            primary_total = 0
            primary_found = 0
            found_files: List[str] = []

            for u_name, u_spec in units.items():
                try:
                    if self.path_resolver:
                        _, dest_path, _, u_type = self.path_resolver.resolve(pkg_name, u_name, u_spec, base_dir)
                    else:
                        u_type = (u_spec or {}).get("type", "file")
                        dest_path = (u_spec or {}).get("dest", "")
                except Exception:
                    continue

                is_primary = u_type in ("script", "symlink", "file", "unit", "service", "timer")
                if is_primary:
                    primary_total += 1

                existing_path = self._probe_unit_on_disk(pkg_name, u_name, dest_path, u_type)
                if existing_path:
                    found_files.append(existing_path)
                    if is_primary:
                        primary_found += 1

            if primary_total > 0 and primary_found == primary_total:
                detected[pkg_name] = {
                    "version": str(pkg_info.get("version", "1.0.0")),
                    "installed_at": 0,
                    "timestamp": "обнаружен в ОС",
                    "files": list(dict.fromkeys(found_files)),
                    "namespace": reg_key,
                    "desc": str(pkg_info.get("description") or pkg_info.get("desc") or ""),
                }
        return detected

    def get_state(self) -> Dict[str, Any]:
        """Возвращает объединенное состояние установленных пакетов (из state.json и проверки файловой системы)."""
        installed: Dict[str, Dict[str, Any]] = {}
        for state_file in self._get_candidate_state_files():
            installed.update(self._read_single_state_file(state_file))

        fs_detected = self._detect_installed_from_filesystem(installed)
        for k, v in fs_detected.items():
            installed.setdefault(k, v)

        # Обогащаем описанием из реестра, если оно не было сохранено в state.json
        if self.registry and getattr(self.registry, "packages", None):
            for pkg_key, entry in installed.items():
                if not entry.get("desc") and self.registry.has(pkg_key):
                    p_info = self.registry.get(pkg_key)
                    entry["desc"] = str(p_info.get("description") or p_info.get("desc") or "")

        return {"installed": installed, "installed_packages": installed}

    def save_state(self, state_data: Dict[str, Any]) -> bool:
        """Сохраняет состояние атомарно с правами чтения 0644."""
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Обновление состояния в {self.state_file_path}")
            return True

        state_dir = os.path.dirname(self.state_file_path)
        os.makedirs(state_dir, exist_ok=True)

        installed_map = state_data.get("installed", {})
        payload = {"installed": installed_map, "installed_packages": installed_map}
        tmp_path = f"{self.state_file_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.state_file_path)
            os.chmod(self.state_file_path, 0o644)
            return True
        except Exception as err:
            self.context.log(f"⚠️ Не удалось сохранить состояние в {self.state_file_path}: {err}")
            return False

    def mark_installed(
        self,
        pkg_name: str,
        version: str,
        files: List[str],
        namespace: Optional[str] = None,
        desc: str = "",
    ) -> None:
        """Регистрирует пакет как установленный."""
        current = self._read_single_state_file(self.state_file_path)
        current[pkg_name] = {
            "version": version,
            "installed_at": time.time(),
            "files": list(dict.fromkeys(files)),
            "namespace": namespace or pkg_name,
            "desc": desc,
        }
        self.save_state({"installed": current})

    def mark_uninstalled(self, pkg_name: str) -> None:
        """Удаляет запись о пакете из состояния."""
        short_name = pkg_name.split("/")[-1]
        for candidate_file in self._get_candidate_state_files():
            if not os.path.exists(candidate_file):
                continue
            entries = self._read_single_state_file(candidate_file)
            keys_to_del = [
                k for k, v in entries.items()
                if k in (pkg_name, short_name) or v.get("namespace") == pkg_name
            ]
            if keys_to_del:
                for k in keys_to_del:
                    del entries[k]
                if candidate_file == self.state_file_path:
                    self.save_state({"installed": entries})
                elif not self.context.dry_run and os.access(candidate_file, os.W_OK):
                    try:
                        with open(candidate_file, "w", encoding="utf-8") as f:
                            json.dump({"installed": entries, "installed_packages": entries}, f, indent=2, ensure_ascii=False)
                    except Exception:
                        pass

    def get_installed_package(self, pkg_name: str) -> Optional[Dict[str, Any]]:
        """Возвращает метаданные установленного пакета по имени или пространству имен."""
        installed = self.get_state().get("installed", {})
        if pkg_name in installed:
            return installed[pkg_name]
        short = pkg_name.split("/")[-1]
        if short in installed:
            return installed[short]
        for entry in installed.values():
            if entry.get("namespace") in (pkg_name, short):
                return entry
        return None
