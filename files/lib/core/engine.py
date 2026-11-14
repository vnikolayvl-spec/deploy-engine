"""
Core Engine facade orchestrating package discovery, dependencies, cross-platform installation, and state.
"""
import os
import shlex
from typing import Any, Dict, List, Optional
from lib.config import DATA_PREFIX, DEFAULT_PACKAGES_DIR, ENV_PREFIX, PACKAGES_CACHE_FILE, PACKAGES_DIR
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.dependencies.dependency_graph import DependencyGraph
from lib.dependencies.node_pkg_manager import NodePackageManager
from lib.dependencies.python_pkg_manager import PythonPackageManager
from lib.dependencies.system_pkg_manager import SystemPackageManager
from lib.discovery.package_registry import PackageRegistry
from lib.env.env_upsert_manager import EnvUpsertManager
from lib.installer.file_installer import FileInstaller
from lib.installer.transaction_manager import TransactionManager
from lib.installer.unit_path_resolver import UnitPathResolver
from lib.lifecycle.hook_executor import HookExecutor
from lib.providers.base_provider import BaseEnvironmentProvider
from lib.providers.provider_factory import EnvironmentProviderFactory
from lib.providers.systemd_to_plist_converter import SystemdToPlistConverter
from lib.state.backup_manager import BackupManager
from lib.state.state_repository import StateRepository


class Engine:
    """Главный фасад оркестрации Deploy Engine с поддержкой провайдеров окружения."""

    def __init__(self, context: Optional[ExecutionContext] = None, provider: Optional[BaseEnvironmentProvider] = None):
        self.context = context or ExecutionContext()
        self.provider = provider or EnvironmentProviderFactory.create(self.context)
        self.registry = PackageRegistry(cache_file=PACKAGES_CACHE_FILE)
        self.dep_graph = DependencyGraph(self.registry)
        self.sys_manager, self.py_manager, self.node_manager = SystemPackageManager(self.context, provider=self.provider), PythonPackageManager(context=self.context), NodePackageManager(context=self.context)
        self.path_resolver, self.txn = UnitPathResolver(provider=self.provider), TransactionManager()
        self.file_installer, self.env_manager, self.hook_executor = FileInstaller(self.context, self.txn, provider=self.provider), EnvUpsertManager(self.context, self.txn, provider=self.provider), HookExecutor(self.context, provider=self.provider)
        self.state_repo = StateRepository(context=self.context, provider=self.provider, registry=self.registry, path_resolver=self.path_resolver)
        self.backup_manager = BackupManager(context=self.context, provider=self.provider, registry=self.registry, path_resolver=self.path_resolver, state_repo=self.state_repo)
        self.files_to_deploy, self.sys_packages_to_install, self.active_packages, self.deployed_files_map = [], [], [], {}

    def configure_environment(self, sandbox: bool = False, sandbox_os: Optional[str] = None) -> None:
        self.context.sandbox = sandbox
        if sandbox_os:
            self.context.sandbox_os = sandbox_os
        self.provider = EnvironmentProviderFactory.create(self.context)
        for mgr in (self.sys_manager, self.path_resolver, self.file_installer, self.file_installer.data_installer, self.env_manager, self.hook_executor):
            mgr.provider = self.provider
        self.state_repo = StateRepository(context=self.context, provider=self.provider, registry=self.registry, path_resolver=self.path_resolver)
        self.backup_manager.provider, self.backup_manager.state_repo = self.provider, self.state_repo

    @property
    def packages(self) -> Dict[str, Dict[str, Any]]: return self.registry.packages

    @property
    def folders(self) -> Dict[str, Dict[str, Any]]: return self.registry.folders

    @property
    def units(self) -> Dict[str, Dict[str, Any]]:
        all_units: Dict[str, Dict[str, Any]] = {}
        for ns, pkg in self.registry.packages.items():
            pkg_name, base_dir = pkg.get("name", ns), pkg.get("base_dir", ".")
            root_dir = os.path.dirname(os.path.abspath(base_dir))
            for u_name, u_spec in pkg.get("units", {}).items():
                enriched = dict(u_spec or {}, base_dir=u_spec.get("base_dir", base_dir), root_dir=u_spec.get("root_dir", root_dir))
                all_units[u_name] = all_units[f"{pkg_name}:{u_name}"] = all_units[f"{ns}:{u_name}"] = enriched
        return all_units

    def is_package_compatible(self, pkg_or_name: Any) -> bool:
        pkg = self.registry.get(pkg_or_name) if isinstance(pkg_or_name, str) else pkg_or_name
        return bool(isinstance(pkg, dict) and self.provider.is_package_compatible(pkg) and self.registry.is_folder_compatible(pkg.get("folder_path", ""), self.provider))

    def discover_packages(self, search_roots: Optional[List[str]] = None, force_rescan: bool = False) -> int:
        if search_roots:
            valid_roots = [r for r in search_roots if os.path.exists(r)]
        else:
            valid_roots, seen_abs = [], set()
            for candidate in (PACKAGES_DIR, DEFAULT_PACKAGES_DIR, "deploy_packages", "deploy_packages/packages"):
                if os.path.exists(candidate):
                    abs_c = os.path.abspath(candidate)
                    if abs_c not in seen_abs and not any(abs_c.startswith(s + os.sep) for s in seen_abs):
                        valid_roots.append(candidate)
                        seen_abs.add(abs_c)
        return self.registry.scan_directories(valid_roots, force_rescan=force_rescan)

    def load_manifest_recursive(self, manifest_or_dir: str) -> int:
        if os.path.isdir(manifest_or_dir):
            return self.discover_packages(search_roots=[manifest_or_dir], force_rescan=True)
        self.registry.load_legacy_manifest(manifest_or_dir)
        return len(self.registry.packages)

    def infer_targets_from_manifest(self, manifest_path: str) -> List[str]:
        if not manifest_path or not os.path.isfile(manifest_path): return []
        try: parsed = self.registry.parser.parse_file(manifest_path)
        except Exception: return []
        if parsed.get("is_category") or parsed.get("is_folder_only"): return []
        if parsed.get("is_multi_package"):
            pkgs = parsed.get("packages", {})
            return [name for name, p in pkgs.items() if not p.get("is_alias")] or list(pkgs.keys())
        return [parsed["name"]] if parsed.get("name") else []

    def load_default_manifests(self) -> int: return self.discover_packages(force_rescan=True)

    def reset_queue(self) -> None:
        for lst in (self.files_to_deploy, self.sys_packages_to_install, self.active_packages, self.deployed_files_map): lst.clear()

    def resolve_dependencies(self, target: str) -> List[str]:
        if not self.registry.has(target):
            return []
        order = self.dep_graph.resolve_order([target])
        for pkg_name in order:
            pkg = self.registry.get(pkg_name)
            if pkg["name"] not in self.active_packages:
                self.active_packages.append(pkg["name"])
            self.sys_packages_to_install.extend([sp for sp in self.sys_manager.resolve_for_platform(pkg.get("sys_packages", [])) if sp not in self.sys_packages_to_install])
            self.files_to_deploy.extend([f"{pkg['name']}:{u}" for u in pkg.get("units", {}) if f"{pkg['name']}:{u}" not in self.files_to_deploy])
        return order

    def get_paths_and_modes(self, unit_ref: str):
        pkg_name, unit_name = unit_ref.split(":", 1) if ":" in unit_ref else (unit_ref, unit_ref)
        pkg = self.registry.get(pkg_name)
        return self.path_resolver.resolve(pkg["name"], unit_name, pkg.get("units", {}).get(unit_name, {}), pkg.get("base_dir"))

    def _rollback_safely(self, reason_msg: str) -> None:
        self.context.log(f"{reason_msg}\n⏪ Запуск отката транзакции (LIFO)...")
        try:
            self.txn.rollback()
            self.context.log("🛡️ Откат транзакции завершен успешно.")
        except Exception as rb_err:
            self.context.log(f"⚠️ Ошибка при откате: {rb_err}")

    def install_packages(self, targets: List[str]) -> bool:
        """Транзакционная установка пакетов с проверкой совместимости ОС и автоматическим откатом."""
        valid_targets = [t for t in (targets or []) if t and str(t).strip() and self.registry.has(str(t).strip())]
        if not valid_targets:
            return False
        ordered_packages = self.dep_graph.resolve_order(valid_targets)
        for pkg_name in ordered_packages:
            pkg = self.registry.get(pkg_name)
            if not self.is_package_compatible(pkg):
                supported = ", ".join(pkg.get("platforms") or [])
                raise DeployEngineError(f"Пакет '{pkg['name']}' не поддерживает текущую систему ({self.provider.distro_id}). Поддерживаемые платформы: {supported}")
        self.context.log(f"📋 Порядок установки пакетов: {' -> '.join(ordered_packages)}")
        all_sys_pkgs: List[str] = []
        for pkg_name in ordered_packages:
            all_sys_pkgs.extend(self.sys_manager.resolve_for_platform(self.registry.get(pkg_name).get("sys_packages", [])))
        if all_sys_pkgs:
            self.sys_manager.install_packages(all_sys_pkgs)
        try:
            for pkg_name in ordered_packages:
                self._install_single_package(pkg_name)
            self.txn.commit()
            self.context.log("🎉 Все пакеты успешно установлены!")
            return True
        except KeyboardInterrupt:
            self._rollback_safely("\n⚠️ Установка прервана пользователем (Ctrl+C).")
            raise
        except Exception as err:
            self._rollback_safely(f"💥 Сбой при установке пакетов: {err}")
            raise DeployEngineError(f"Установка прервана: {err}")

    def _install_single_package(self, pkg_name: str) -> None:
        """Установка пакета: ENV -> файлы/скрипты/каталоги -> службы (systemd или launchd .plist) -> хуки."""
        pkg = self.registry.get(pkg_name)
        canonical_name, base_dir = pkg["name"], os.path.abspath(pkg.get("base_dir", "."))
        paths = self.provider.get_paths()
        opt_pkg_dir = os.path.join(paths.get("opt_dir", "/opt"), f"de_{canonical_name}")
        env_pkg_dir = os.path.join(paths["env_path"], f"{ENV_PREFIX}{canonical_name}")
        data_pkg_dir = os.path.join(paths["state_dir"], f"{DATA_PREFIX}{canonical_name}")
        data_dir_existed = os.path.exists(data_pkg_dir)

        with self.context.package_operation_log(data_pkg_dir, canonical_name, getattr(self, "_current_op", "install")) as op_log:
            if op_log and not data_dir_existed:
                self.txn.record_created_dir(data_pkg_dir)
            self.context.log(f"\n🚀 Развертывание пакета: {canonical_name} (версия {pkg.get('version', '1.0.0')})")
            if pkg.get("python_packages"): self.py_manager.install(pkg["python_packages"], base_dir)
            if pkg.get("node_packages"): self.node_manager.install(pkg["node_packages"], base_dir)
            if pkg.get("pre_install"): self.hook_executor.run_hook("pre_install", pkg["pre_install"], canonical_name, base_dir)

            context_vars = {
                "{{ROOT_DIR}}": os.path.dirname(base_dir), "{{BASE_DIR}}": base_dir, "{{SYS_BIN}}": paths["sys_bin"],
                "{{SYS_SYSTEMD}}": paths["sys_systemd"], "{{ENV_PATH}}": paths["env_path"], "{{STATE_DIR}}": paths["state_dir"],
                "{{OPT_DIR}}": paths.get("opt_dir", "/opt"), "{{ENV_DIR}}": env_pkg_dir, "{{DATA_DIR}}": data_pkg_dir,
            }
            installed_files, static_env_vars, service_units, timer_units = [], {}, {}, {}

            def _track_path(p: str, u_type: str) -> None:
                for parent_dir in (opt_pkg_dir, env_pkg_dir, data_pkg_dir):
                    if p.startswith(parent_dir + os.sep) and parent_dir not in installed_files:
                        installed_files.append(parent_dir)
                        self.deployed_files_map[parent_dir] = "dir"
                if p not in installed_files:
                    installed_files.append(p)
                self.deployed_files_map[p] = u_type

            for unit_name, unit_spec in pkg.get("units", {}).items():
                src_path, dest_path, mode, unit_type = self.path_resolver.resolve(canonical_name, unit_name, unit_spec, base_dir)
                if unit_type == "env":
                    self.env_manager.upsert_env_file(src_path, dest_path, pkg_name=canonical_name)
                    static_env_vars.update(SystemdToPlistConverter.parse_env_file(dest_path if os.path.isfile(dest_path) else src_path))
                    _track_path(dest_path, unit_type)
                elif self.provider.uses_launchd_plist() and unit_type in ("unit", "service", "timer"):
                    stem = SystemdToPlistConverter.get_service_stem(unit_name)
                    (timer_units if (unit_type == "timer" or unit_name.endswith(".timer")) else service_units)[stem] = (unit_name, src_path, dest_path, mode)
                else:
                    symlink_target = (unit_spec.get("symlink") or unit_spec.get("src")) if unit_type == "symlink" else None
                    if symlink_target:
                        for marker, real_val in context_vars.items():
                            symlink_target = str(symlink_target).replace(marker, real_val)
                    self.file_installer.install_file(src_path, dest_path, mode, unit_type, symlink_target, context_vars=context_vars)
                    _track_path(dest_path, unit_type)

            for d_path in self.file_installer.apply_declarative_dirs_and_chmod(pkg.get("dirs", []), pkg.get("chmod", []), context_vars):
                _track_path(d_path, "dir")
            if self.provider.uses_launchd_plist() and (service_units or timer_units):
                for p_path in self.file_installer.install_launchd_plists(canonical_name, service_units, timer_units, static_env_vars, context_vars):
                    _track_path(p_path, "plist")
            if pkg.get("post_install"):
                self.hook_executor.run_hook("post_install", pkg["post_install"], canonical_name, base_dir)
            mf_path = pkg.get("manifest_path") or os.path.join(base_dir, "manifest.json")
            self.state_repo.mark_installed(canonical_name, pkg.get("version", "1.0.0"), installed_files, pkg.get("namespace"), desc=pkg.get("desc", ""), manifest_path=mf_path)

    def install_files(self) -> None:
        pkgs_in_queue = list(dict.fromkeys([f.split(":", 1)[0] for f in self.files_to_deploy if ":" in f])) or list(self.active_packages)
        if pkgs_in_queue:
            self.install_packages(pkgs_in_queue)

    def _stop_package_services(self, canonical_name: str, files_to_remove: List[str], base_dir: str) -> bool:
        stop_cmds = [
            f"launchctl unload -w {shlex.quote(f)} 2>/dev/null || true" if (self.provider.uses_launchd_plist() and f.endswith(".plist")) else f"systemctl disable --now {shlex.quote(os.path.basename(f))} 2>/dev/null || true"
            for f in files_to_remove if (self.provider.uses_launchd_plist() and f.endswith(".plist")) or f.endswith((".service", ".timer"))
        ]
        if stop_cmds:
            self.hook_executor.run_hook("stop_services", stop_cmds, canonical_name, base_dir)
        return any(f.endswith((".service", ".timer")) for f in files_to_remove) and not self.provider.uses_launchd_plist()

    def uninstall_package(self, pkg_name: str) -> bool:
        """Удаление пакета с проверкой на пустоту, авто-остановкой служб и выводом оставшихся папок."""
        raw_target = (pkg_name or "").strip()
        if not raw_target or "*" in raw_target or raw_target in (".", "..", "/"):
            raise DeployEngineError("Некорректное или пустое имя пакета для удаления.")
        pkg_info = self.registry.get(raw_target) if self.registry.has(raw_target) else None
        canonical_name, base_dir = (pkg_info["name"].strip(), pkg_info.get("base_dir", ".")) if pkg_info else (raw_target.split("/")[-1].strip(), ".")
        if not canonical_name or "/" in canonical_name or "*" in canonical_name or canonical_name in (".", ".."):
            raise DeployEngineError(f"Некорректное каноническое имя пакета для удаления: '{canonical_name}'")

        paths = self.provider.get_paths()
        state_entry = self.state_repo.get_installed_package(canonical_name)
        raw_files = list(state_entry.get("files", []) if state_entry else [])
        for u_name, u_spec in (pkg_info.get("units", {}) if pkg_info else {}).items():
            _, dest, _, _ = self.path_resolver.resolve(canonical_name, u_name, u_spec, base_dir)
            if dest and dest not in raw_files:
                raw_files.append(dest)

        files_to_remove = list(dict.fromkeys([str(f).strip() for f in raw_files if f and str(f).strip()]))
        if not state_entry and not pkg_info and not files_to_remove:
            self.context.log(f"\n🗑️ Удаление пакета: {canonical_name}\n⚠️ Пакет '{canonical_name}' не найден в установленных и список файлов на удаление пуст.")
            return False

        data_pkg_dir = os.path.join(paths["state_dir"], f"{DATA_PREFIX}{canonical_name}")
        with self.context.package_operation_log("" if self.context.purge else data_pkg_dir, canonical_name, "uninstall"):
            self.context.log(f"\n🗑️ Удаление пакета: {canonical_name}")
            has_systemd = self._stop_package_services(canonical_name, files_to_remove, base_dir)
            if pkg_info and pkg_info.get("pre_uninstall"): self.hook_executor.run_hook("pre_uninstall", pkg_info["pre_uninstall"], canonical_name, base_dir)
            opt_pkg_dir = os.path.join(paths.get("opt_dir", "/opt"), f"de_{canonical_name}")
            for dest_file in reversed(files_to_remove):
                if dest_file == opt_pkg_dir or ((paths["env_path"] in dest_file or "/etc/default/" in dest_file or paths["state_dir"] in dest_file or "/var/lib/" in dest_file) and not self.context.purge):
                    continue
                self.file_installer.remove_file(dest_file)
            if os.path.isdir(opt_pkg_dir) and FileInstaller.is_safe_to_remove(opt_pkg_dir) and not os.listdir(opt_pkg_dir):
                self.file_installer.remove_file(opt_pkg_dir)
            if has_systemd: self.hook_executor.run_hook("daemon_reload", ["systemctl daemon-reload 2>/dev/null || true"], canonical_name, base_dir)
            self.env_manager.remove_env(canonical_name, purge=self.context.purge)
            self.file_installer.data_installer.remove_data(canonical_name, purge=self.context.purge)
            if pkg_info and pkg_info.get("post_uninstall"): self.hook_executor.run_hook("post_uninstall", pkg_info["post_uninstall"], canonical_name, base_dir)
            self.state_repo.mark_uninstalled(canonical_name)
            rem_dirs = [d for d in (os.path.join(paths["env_path"], f"{ENV_PREFIX}{canonical_name}"), data_pkg_dir, opt_pkg_dir) if os.path.exists(d)]
            if rem_dirs:
                self.context.log(f"📌 Оставшиеся системные каталоги пакета '{canonical_name}': {', '.join(rem_dirs)}")
                self.context.log(f"👉 Для их ручного удаления выполните: sudo rm -rf {' '.join(shlex.quote(d) for d in rem_dirs)}")
            self.context.log(f"✅ Пакет {canonical_name} успешно удален.")
        return True

    def reinstall_package(self, pkg_name: str) -> bool:
        self.context.log(f"\n🔄 Переустановка пакета: {pkg_name}")
        self.uninstall_package(pkg_name)
        self._current_op = "reinstall"
        try: return self.install_packages([pkg_name])
        finally: self._current_op = "install"

    def backup_packages(self, targets: List[str], comment: str = "") -> List[Dict[str, Any]]:
        resolved = self.backup_manager.resolve_targets(targets, for_restore=False)
        if not resolved: raise DeployEngineError("Не найдено установленных пакетов с данными или .env для резервного копирования.")
        return [self.backup_manager.create_backup(pkg, comment=comment) for pkg in resolved]

    def restore_packages(self, targets: List[str], selector: Optional[str] = None) -> List[Dict[str, Any]]:
        resolved = self.backup_manager.resolve_targets(targets, for_restore=True)
        if not resolved: raise DeployEngineError("Не найдено пакетов с доступными бэкапами для восстановления.")
        return [self.backup_manager.restore_backup(pkg, selector=selector) for pkg in resolved]
