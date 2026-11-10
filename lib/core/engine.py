"""
Core Engine facade orchestrating package discovery, dependencies, installation, and state.
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
from lib.state.state_repository import StateRepository


class Engine:
    """Главный фасад оркестрации Deploy Engine 2.0."""

    def __init__(self, context: Optional[ExecutionContext] = None):
        self.context = context or ExecutionContext()
        self.registry = PackageRegistry(cache_file=PACKAGES_CACHE_FILE)
        self.dep_graph = DependencyGraph(self.registry)
        self.sys_manager = SystemPackageManager(self.context)
        self.py_manager = PythonPackageManager(context=self.context)
        self.node_manager = NodePackageManager(context=self.context)
        self.path_resolver = UnitPathResolver()
        self.txn = TransactionManager()
        self.file_installer = FileInstaller(self.context, self.txn)
        self.env_manager = EnvUpsertManager(self.context, self.txn)
        self.hook_executor = HookExecutor(self.context)
        self.state_repo = StateRepository(context=self.context)

        # Совместимость с очередями v1
        self.files_to_deploy: List[str] = []
        self.sys_packages_to_install: List[str] = []

    @property
    def packages(self) -> Dict[str, Dict[str, Any]]:
        """Доступ к зарегистрированным пакетам для обратной совместимости."""
        return self.registry.packages

    @property
    def folders(self) -> Dict[str, Dict[str, Any]]:
        """Доступ к метаданным папок (desc, base_dir)."""
        return self.registry.folders

    @property
    def units(self) -> Dict[str, Dict[str, Any]]:
        """Агрегированный словарь всех зарегистрированных юнитов для обратной совместимости."""
        all_units: Dict[str, Dict[str, Any]] = {}
        for pkg in self.registry.packages.values():
            all_units.update(pkg.get("units", {}))
        return all_units

    def discover_packages(self, search_roots: Optional[List[str]] = None, force_rescan: bool = False) -> int:
        """Обнаруживает и регистрирует пакеты в реестре."""
        roots = search_roots or [PACKAGES_DIR, DEFAULT_PACKAGES_DIR, "deploy_packages"]
        valid_roots = [r for r in roots if os.path.exists(r)]
        return self.registry.scan_directories(valid_roots, force_rescan=force_rescan)

    def load_manifest_recursive(self, manifest_path: str) -> None:
        """Обратная совместимость: прямая загрузка файла манифеста."""
        self.registry.load_legacy_manifest(manifest_path)

    def load_default_manifests(self) -> int:
        """Обратная совместимость для TUI: обнаружение и загрузка пакетов по умолчанию."""
        return self.discover_packages()

    def reset_queue(self) -> None:
        """Сброс очереди файлов и системных пакетов."""
        self.files_to_deploy.clear()
        self.sys_packages_to_install.clear()

    def resolve_dependencies(self, target: str) -> List[str]:
        """Разрешает зависимости и наполняет очередь установки."""
        order = self.dep_graph.resolve_order([target])
        for pkg_name in order:
            pkg = self.registry.get(pkg_name)
            # Добавляем системные пакеты
            for sp in pkg.get("sys_packages", []):
                if sp not in self.sys_packages_to_install:
                    self.sys_packages_to_install.append(sp)
            # Добавляем юниты в очередь
            for unit_name in pkg.get("units", {}).keys():
                unit_ref = f"{pkg['name']}:{unit_name}"
                if unit_ref not in self.files_to_deploy:
                    self.files_to_deploy.append(unit_ref)
        return order

    def get_paths_and_modes(self, unit_ref: str):
        """Обратная совместимость: возвращает (src, dest, mode, unit_type)."""
        pkg_name, unit_name = unit_ref.split(":", 1)
        pkg = self.registry.get(pkg_name)
        unit_spec = pkg.get("units", {}).get(unit_name, {})
        pkg_base_dir = pkg.get("base_dir")
        return self.path_resolver.resolve(pkg_name, unit_name, unit_spec, pkg_base_dir)

    def install_packages(self, targets: List[str]) -> bool:
        """
        Транзакционная безопасная установка нескольких пакетов с автоматическим откатом.
        """
        ordered_packages = self.dep_graph.resolve_order(targets)
        self.context.log(f"📋 Порядок установки пакетов: {' -> '.join(ordered_packages)}")

        # 1. Агрегация и пакетная установка системных зависимостей ОС
        all_sys_pkgs: List[str] = []
        for pkg_name in ordered_packages:
            all_sys_pkgs.extend(self.registry.get(pkg_name).get("sys_packages", []))
        if all_sys_pkgs:
            self.sys_manager.install_packages(all_sys_pkgs)

        try:
            # 2. Установка каждого пакета в топологическом порядке
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
        """Установка отдельного пакета со всеми юнитами, хуками и ENV."""
        pkg = self.registry.get(pkg_name)
        base_dir = pkg.get("base_dir", ".")
        self.context.log(f"\n🚀 Развертывание пакета: {pkg_name} (версия {pkg.get('version', '1.0.0')})")

        # Python & Node dependencies
        if pkg.get("python_packages"):
            self.py_manager.install(pkg["python_packages"], base_dir)
        if pkg.get("node_packages"):
            self.node_manager.install(pkg["node_packages"], base_dir)

        # Pre-install hook
        if pkg.get("pre_install"):
            self.hook_executor.run_hook("pre_install", pkg["pre_install"], pkg_name, base_dir)

        installed_files: List[str] = []

        # Units deployment
        for unit_name, unit_spec in pkg.get("units", {}).items():
            src_path, dest_path, mode, unit_type = self.path_resolver.resolve(
                pkg_name, unit_name, unit_spec, base_dir
            )

            if unit_type == "env":
                self.env_manager.upsert_env_file(src_path, dest_path)
            else:
                symlink_target = unit_spec.get("symlink") if unit_type == "symlink" else None
                self.file_installer.install_file(src_path, dest_path, mode, unit_type, symlink_target)

            installed_files.append(dest_path)

        # Post-install hook
        if pkg.get("post_install"):
            self.hook_executor.run_hook("post_install", pkg["post_install"], pkg_name, base_dir)

        # Запись в репозиторий состояния
        self.state_repo.mark_installed(pkg_name, pkg.get("version", "1.0.0"), installed_files, pkg.get("namespace"))

    def install_files(self) -> None:
        """Обратная совместимость: установка по текущей очереди files_to_deploy."""
        if self.sys_packages_to_install:
            self.sys_manager.install_packages(self.sys_packages_to_install)

        pkgs_in_queue = list(dict.fromkeys([f.split(":", 1)[0] for f in self.files_to_deploy]))
        for pkg_name in pkgs_in_queue:
            self._install_single_package(pkg_name)
        self.txn.commit()

    def uninstall_package(self, pkg_name: str) -> bool:
        """Удаление пакета: юниты и скрипты удаляются, ENV и Data сохраняются (если не purge)."""
        self.context.log(f"\n🗑️ Удаление пакета: {pkg_name}")
        pkg_info = self.registry.get(pkg_name) if self.registry.has(pkg_name) else None
        base_dir = pkg_info.get("base_dir", ".") if pkg_info else "."

        # Pre-uninstall hook
        if pkg_info and pkg_info.get("pre_uninstall"):
            self.hook_executor.run_hook("pre_uninstall", pkg_info["pre_uninstall"], pkg_name, base_dir)

        # Удаление файлов из состояния или манифеста
        state_entry = self.state_repo.get_installed_package(pkg_name)
        files_to_remove = state_entry.get("files", []) if state_entry else []

        if not files_to_remove and pkg_info:
            for u_name, u_spec in pkg_info.get("units", {}).items():
                _, dest, _, _ = self.path_resolver.resolve(pkg_name, u_name, u_spec, base_dir)
                files_to_remove.append(dest)

        for dest_file in files_to_remove:
            # Не удаляем ENV и Data файлы, если не включен --purge
            if "/etc/default/" in dest_file and not self.context.purge:
                continue
            if "/var/lib/" in dest_file and not self.context.purge:
                continue
            self.file_installer.remove_file(dest_file)

        # Очистка ENV и данных с учетом purge
        self.env_manager.remove_env(pkg_name, purge=self.context.purge)
        self.file_installer.data_installer.remove_data(pkg_name, purge=self.context.purge)

        # Post-uninstall hook
        if pkg_info and pkg_info.get("post_uninstall"):
            self.hook_executor.run_hook("post_uninstall", pkg_info["post_uninstall"], pkg_name, base_dir)

        self.state_repo.mark_uninstalled(pkg_name)
        self.context.log(f"✅ Пакет {pkg_name} успешно удален.")
        return True

    def reinstall_package(self, pkg_name: str) -> bool:
        """Переустановка пакета с сохранением существующих секретов и данных."""
        self.context.log(f"\n🔄 Переустановка пакета: {pkg_name}")
        self.uninstall_package(pkg_name)
        return self.install_packages([pkg_name])
