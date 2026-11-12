"""
Core Engine facade orchestrating package discovery, dependencies, cross-platform installation, and state.
"""
import os
from typing import Any, Dict, List, Optional
from deploy_config import DEFAULT_PACKAGES_DIR, PACKAGES_CACHE_FILE, PACKAGES_DIR
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
from lib.state.state_repository import StateRepository


class Engine:
    """Главный фасад оркестрации Deploy Engine с поддержкой провайдеров окружения."""

    def __init__(self, context: Optional[ExecutionContext] = None, provider: Optional[BaseEnvironmentProvider] = None):
        self.context = context or ExecutionContext()
        self.provider = provider or EnvironmentProviderFactory.create(self.context)
        self.registry = PackageRegistry(cache_file=PACKAGES_CACHE_FILE)
        self.dep_graph = DependencyGraph(self.registry)
        self.sys_manager = SystemPackageManager(self.context, provider=self.provider)
        self.py_manager = PythonPackageManager(context=self.context)
        self.node_manager = NodePackageManager(context=self.context)
        self.path_resolver = UnitPathResolver(provider=self.provider)
        self.txn = TransactionManager()
        self.file_installer = FileInstaller(self.context, self.txn, provider=self.provider)
        self.env_manager = EnvUpsertManager(self.context, self.txn, provider=self.provider)
        self.hook_executor = HookExecutor(self.context, provider=self.provider)
        self.state_repo = StateRepository(context=self.context, provider=self.provider, registry=self.registry, path_resolver=self.path_resolver)
        self.files_to_deploy: List[str] = []
        self.sys_packages_to_install: List[str] = []
        self.active_packages: List[str] = []
        self.deployed_files_map: Dict[str, str] = {}

    def configure_environment(self, sandbox: bool = False, sandbox_os: Optional[str] = None) -> None:
        """Динамически переключает режим песочницы и эмулируемую ОС во всех подсистемах движка."""
        self.context.sandbox = sandbox
        if sandbox_os:
            self.context.sandbox_os = sandbox_os
        self.provider = EnvironmentProviderFactory.create(self.context)
        for mgr in (self.sys_manager, self.path_resolver, self.file_installer, self.file_installer.data_installer, self.env_manager, self.hook_executor):
            mgr.provider = self.provider
        self.state_repo = StateRepository(context=self.context, provider=self.provider, registry=self.registry, path_resolver=self.path_resolver)

    @property
    def packages(self) -> Dict[str, Dict[str, Any]]:
        return self.registry.packages

    @property
    def folders(self) -> Dict[str, Dict[str, Any]]:
        return self.registry.folders

    @property
    def units(self) -> Dict[str, Dict[str, Any]]:
        """Агрегированный словарь всех зарегистрированных юнитов для обратной совместимости."""
        all_units: Dict[str, Dict[str, Any]] = {}
        for ns, pkg in self.registry.packages.items():
            pkg_name, base_dir = pkg.get("name", ns), pkg.get("base_dir", ".")
            root_dir = os.path.dirname(os.path.abspath(base_dir))
            for u_name, u_spec in pkg.get("units", {}).items():
                enriched = dict(u_spec or {})
                enriched.setdefault("base_dir", base_dir)
                enriched.setdefault("root_dir", root_dir)
                all_units[u_name] = all_units[f"{pkg_name}:{u_name}"] = all_units[f"{ns}:{u_name}"] = enriched
        return all_units

    def is_package_compatible(self, pkg_or_name: Any) -> bool:
        """Проверяет, поддерживается ли пакет и вся цепочка его родительских категорий активным провайдером ОС."""
        pkg = self.registry.get(pkg_or_name) if isinstance(pkg_or_name, str) else pkg_or_name
        if not isinstance(pkg, dict) or not self.provider.is_package_compatible(pkg):
            return False
        return self.registry.is_folder_compatible(pkg.get("folder_path", ""), self.provider)

    def discover_packages(self, search_roots: Optional[List[str]] = None, force_rescan: bool = False) -> int:
        """Обнаруживает и регистрирует пакеты и подкатегории (включая папки без корневого манифеста)."""
        if search_roots:
            valid_roots = [r for r in search_roots if os.path.exists(r)]
        else:
            candidates = [PACKAGES_DIR, DEFAULT_PACKAGES_DIR, "deploy_packages", "deploy_packages/packages"]
            valid_roots, seen_abs = [], set()
            for candidate in candidates:
                if os.path.exists(candidate):
                    abs_c = os.path.abspath(candidate)
                    if abs_c not in seen_abs and not any(abs_c.startswith(s + os.sep) for s in seen_abs):
                        valid_roots.append(candidate)
                        seen_abs.add(abs_c)
        return self.registry.scan_directories(valid_roots, force_rescan=force_rescan)

    def load_manifest_recursive(self, manifest_or_dir: str) -> int:
        """Прямая загрузка файла манифеста или корневой папки дерева пакетов."""
        if os.path.isdir(manifest_or_dir):
            return self.discover_packages(search_roots=[manifest_or_dir], force_rescan=True)
        self.registry.load_legacy_manifest(manifest_or_dir)
        return len(self.registry.packages)

    def infer_targets_from_manifest(self, manifest_path: str) -> List[str]:
        """Определяет имена пакетов непосредственно из указанного файла манифеста пакета."""
        if not manifest_path or not os.path.isfile(manifest_path):
            return []
        try:
            parsed = self.registry.parser.parse_file(manifest_path)
        except Exception:
            return []
        if parsed.get("is_category") or parsed.get("is_folder_only"):
            return []
        if parsed.get("is_multi_package"):
            pkgs = parsed.get("packages", {})
            non_aliases = [name for name, p in pkgs.items() if not p.get("is_alias")]
            return non_aliases if non_aliases else list(pkgs.keys())
        return [parsed["name"]] if parsed.get("name") else []

    def load_default_manifests(self) -> int:
        return self.discover_packages(force_rescan=True)

    def reset_queue(self) -> None:
        self.files_to_deploy.clear()
        self.sys_packages_to_install.clear()
        self.active_packages.clear()
        self.deployed_files_map.clear()

    def resolve_dependencies(self, target: str) -> List[str]:
        """Разрешает зависимости и наполняет очередь установки с учетом текущей ОС."""
        if not self.registry.has(target):
            return []
        order = self.dep_graph.resolve_order([target])
        for pkg_name in order:
            pkg = self.registry.get(pkg_name)
            if pkg["name"] not in self.active_packages:
                self.active_packages.append(pkg["name"])
            for sp in self.sys_manager.resolve_for_platform(pkg.get("sys_packages", [])):
                if sp not in self.sys_packages_to_install:
                    self.sys_packages_to_install.append(sp)
            for unit_name in pkg.get("units", {}).keys():
                unit_ref = f"{pkg['name']}:{unit_name}"
                if unit_ref not in self.files_to_deploy:
                    self.files_to_deploy.append(unit_ref)
        return order

    def get_paths_and_modes(self, unit_ref: str):
        pkg_name, unit_name = unit_ref.split(":", 1) if ":" in unit_ref else (unit_ref, unit_ref)
        pkg = self.registry.get(pkg_name)
        return self.path_resolver.resolve(pkg["name"], unit_name, pkg.get("units", {}).get(unit_name, {}), pkg.get("base_dir"))

    def install_packages(self, targets: List[str]) -> bool:
        """Транзакционная установка пакетов с проверкой совместимости ОС и автоматическим откатом."""
        valid_targets = [t for t in targets if self.registry.has(t)]
        if not valid_targets:
            return False

        ordered_packages = self.dep_graph.resolve_order(valid_targets)
        for pkg_name in ordered_packages:
            pkg = self.registry.get(pkg_name)
            if not self.is_package_compatible(pkg):
                supported = ", ".join(pkg.get("platforms") or [])
                raise DeployEngineError(
                    f"Пакет '{pkg['name']}' не поддерживает текущую систему ({self.provider.distro_id}). "
                    f"Поддерживаемые платформы: {supported}"
                )

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
        except Exception as err:
            self.context.log(f"💥 Сбой при установке пакетов: {err}")
            self.context.log("⏪ Запуск отката транзакции (LIFO)...")
            try:
                self.txn.rollback()
                self.context.log("🛡️ Откат транзакции завершен успешно.")
            except Exception as rb_err:
                self.context.log(f"⚠️ Ошибка при откате: {rb_err}")
            raise DeployEngineError(f"Установка прервана: {err}")

    def _install_single_package(self, pkg_name: str) -> None:
        """Установка пакета: ENV -> файлы/скрипты -> службы (systemd или launchd .plist) -> хуки."""
        pkg = self.registry.get(pkg_name)
        canonical_name, base_dir = pkg["name"], os.path.abspath(pkg.get("base_dir", "."))
        paths = self.provider.get_paths()
        self.context.log(f"\n🚀 Развертывание пакета: {canonical_name} (версия {pkg.get('version', '1.0.0')})")

        if pkg.get("python_packages"):
            self.py_manager.install(pkg["python_packages"], base_dir)
        if pkg.get("node_packages"):
            self.node_manager.install(pkg["node_packages"], base_dir)
        if pkg.get("pre_install"):
            self.hook_executor.run_hook("pre_install", pkg["pre_install"], canonical_name, base_dir)

        installed_files: List[str] = []
        context_vars = {
            "{{ROOT_DIR}}": os.path.dirname(base_dir),
            "{{BASE_DIR}}": base_dir,
            "{{SYS_BIN}}": paths["sys_bin"],
            "{{SYS_SYSTEMD}}": paths["sys_systemd"],
        }
        static_env_vars: Dict[str, str] = {}
        service_units: Dict[str, tuple] = {}
        timer_units: Dict[str, tuple] = {}

        for unit_name, unit_spec in pkg.get("units", {}).items():
            src_path, dest_path, mode, unit_type = self.path_resolver.resolve(canonical_name, unit_name, unit_spec, base_dir)
            if unit_type == "env":
                self.env_manager.upsert_env_file(src_path, dest_path, pkg_name=canonical_name)
                env_source = dest_path if os.path.isfile(dest_path) else src_path
                static_env_vars.update(SystemdToPlistConverter.parse_env_file(env_source))
                installed_files.append(dest_path)
                self.deployed_files_map[dest_path] = unit_type
            elif self.provider.uses_launchd_plist() and unit_type in ("unit", "service", "timer"):
                stem = SystemdToPlistConverter.get_service_stem(unit_name)
                target_dict = timer_units if (unit_type == "timer" or unit_name.endswith(".timer")) else service_units
                target_dict[stem] = (unit_name, src_path, dest_path, mode)
            else:
                symlink_target = (unit_spec.get("symlink") or unit_spec.get("src")) if unit_type == "symlink" else None
                if symlink_target:
                    for marker, real_val in context_vars.items():
                        symlink_target = str(symlink_target).replace(marker, real_val)
                self.file_installer.install_file(src_path, dest_path, mode, unit_type, symlink_target, context_vars=context_vars)
                installed_files.append(dest_path)
                self.deployed_files_map[dest_path] = unit_type

        if self.provider.uses_launchd_plist() and (service_units or timer_units):
            for p_path in self.file_installer.install_launchd_plists(canonical_name, service_units, timer_units, static_env_vars, context_vars):
                installed_files.append(p_path)
                self.deployed_files_map[p_path] = "plist"

        if pkg.get("post_install"):
            self.hook_executor.run_hook("post_install", pkg["post_install"], canonical_name, base_dir)
        self.state_repo.mark_installed(canonical_name, pkg.get("version", "1.0.0"), installed_files, pkg.get("namespace"))

    def install_files(self) -> None:
        pkgs_in_queue = list(dict.fromkeys([f.split(":", 1)[0] for f in self.files_to_deploy if ":" in f])) or list(self.active_packages)
        if pkgs_in_queue:
            self.install_packages(pkgs_in_queue)

    def uninstall_package(self, pkg_name: str) -> bool:
        """Удаление пакета: юниты и скрипты удаляются, ENV и Data сохраняются (если не purge)."""
        pkg_info = self.registry.get(pkg_name) if self.registry.has(pkg_name) else None
        canonical_name = pkg_info["name"] if pkg_info else pkg_name
        base_dir = pkg_info.get("base_dir", ".") if pkg_info else "."
        paths = self.provider.get_paths()
        self.context.log(f"\n🗑️ Удаление пакета: {canonical_name}")

        if pkg_info and pkg_info.get("pre_uninstall"):
            self.hook_executor.run_hook("pre_uninstall", pkg_info["pre_uninstall"], canonical_name, base_dir)

        state_entry = self.state_repo.get_installed_package(canonical_name)
        files_to_remove = list(dict.fromkeys(state_entry.get("files", []) if state_entry else []))
        if not files_to_remove and pkg_info:
            for u_name, u_spec in pkg_info.get("units", {}).items():
                _, dest, _, _ = self.path_resolver.resolve(canonical_name, u_name, u_spec, base_dir)
                if dest not in files_to_remove:
                    files_to_remove.append(dest)

        for dest_file in files_to_remove:
            if (paths["env_path"] in dest_file or "/etc/default/" in dest_file) and not self.context.purge:
                continue
            if (paths["state_dir"] in dest_file or "/var/lib/" in dest_file) and not self.context.purge:
                continue
            self.file_installer.remove_file(dest_file)

        self.env_manager.remove_env(canonical_name, purge=self.context.purge)
        self.file_installer.data_installer.remove_data(canonical_name, purge=self.context.purge)

        if pkg_info and pkg_info.get("post_uninstall"):
            self.hook_executor.run_hook("post_uninstall", pkg_info["post_uninstall"], canonical_name, base_dir)

        self.state_repo.mark_uninstalled(canonical_name)
        self.context.log(f"✅ Пакет {canonical_name} успешно удален.")
        return True

    def reinstall_package(self, pkg_name: str) -> bool:
        self.context.log(f"\n🔄 Переустановка пакета: {pkg_name}")
        self.uninstall_package(pkg_name)
        return self.install_packages([pkg_name])
