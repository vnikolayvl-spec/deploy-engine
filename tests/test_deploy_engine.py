import json
import os
import shutil
import tempfile
import unittest

from lib.core.dependency_cycle_error import DependencyCycleError
from lib.core.execution_context import ExecutionContext
from lib.core.name_collision_error import NameCollisionError
from lib.dependencies.dependency_graph import DependencyGraph
from lib.discovery.directory_crawler import DirectoryCrawler
from lib.discovery.name_collision_resolver import NameCollisionResolver
from lib.discovery.package_cache_manager import PackageCacheManager
from lib.discovery.package_registry import PackageRegistry
from lib.engine import Engine
from lib.env.env_upsert_manager import EnvUpsertManager
from lib.installer.data_unit_installer import DataUnitInstaller
from lib.installer.file_installer import FileInstaller
from lib.installer.transaction_manager import TransactionManager
from lib.installer.unit_path_resolver import UnitPathResolver
from lib.state.package_inspector import PackageInspector
from lib.state.state_repository import StateRepository


class TestDeployEngineCore(unittest.TestCase):
    """Тесты ядра оркестрации с использованием абстрактных тестовых манифестов."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_core_test_")
        self.engine = Engine()

        self.manifest_path = os.path.join(self.test_dir, "manifest.json")
        sample_manifest = {
            "packages": {
                "base-core": {
                    "desc": "Базовый системный сервис ядра",
                    "sys_packages": ["curl", "jq", "tmux"],
                    "include": ["deploy.env", "service.sh", "files"]
                },
                "worker-service": {
                    "desc": "Автономный фоновый обработчик",
                    "requires": ["base-core"],
                    "include": ["worker.sh", "worker.service"]
                },
                "bundle-meta": {
                    "desc": "Мета-пакет объединения сервисов",
                    "requires": ["base-core", "worker-service"],
                    "include": []
                }
            },
            "units": {
                "deploy.env": {"type": "env", "desc": "Шаблон переменных окружения"},
                "service.sh": {"type": "script", "desc": "Системный исполняемый скрипт"},
                "files": {"type": "file", "desc": "Файлы приложения"},
                "worker.sh": {"type": "script", "desc": "Скрипт воркера"},
                "worker.service": {"type": "unit", "desc": "Служба systemd"}
            }
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(sample_manifest, f, indent=2)

        self.engine.load_manifest_recursive(self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_abstract_packages_loaded(self):
        self.assertIn("base-core", self.engine.packages)
        self.assertIn("worker-service", self.engine.packages)
        self.assertIn("bundle-meta", self.engine.packages)

    def test_engine_units_property_compatibility(self):
        units = self.engine.units
        self.assertIsInstance(units, dict)
        self.assertIn("service.sh", units)
        self.assertIn("base-core:service.sh", units)
        self.assertIn("deploy.env", units)

    def test_load_default_manifests_alias(self):
        res = self.engine.load_default_manifests()
        self.assertIsInstance(res, int)

    def test_default_unit_paths_resolution(self):
        """Проверка путей по умолчанию для script, env, unit и file ('files')."""
        self.engine.files_to_deploy.clear()
        self.engine.resolve_dependencies("base-core")

        _, dest_script, mode_s, type_s = self.engine.get_paths_and_modes("base-core:service.sh")
        self.assertEqual(type_s, "script")
        self.assertEqual(mode_s, 0o755)
        self.assertEqual(dest_script, "/usr/local/bin/service.sh")

        _, dest_env, mode_e, type_e = self.engine.get_paths_and_modes("base-core:deploy.env")
        self.assertEqual(type_e, "env")
        self.assertEqual(mode_e, 0o600)
        self.assertEqual(dest_env, "/etc/default/de_base-core/base-core.env")

        _, dest_files, mode_f, type_f = self.engine.get_paths_and_modes("base-core:files")
        self.assertEqual(type_f, "file")
        self.assertEqual(mode_f, 0o644)
        self.assertEqual(dest_files, "/opt/de_base-core/files")

        _, dest_unit, _, type_u = self.engine.get_paths_and_modes("worker-service:worker.service")
        self.assertEqual(type_u, "unit")
        self.assertEqual(dest_unit, "/etc/systemd/system/worker.service")

    def test_sys_packages_collection(self):
        self.engine.reset_queue()
        self.engine.resolve_dependencies("base-core")
        self.assertIn("curl", self.engine.sys_packages_to_install)

    def test_dependency_chain_and_meta_bundle(self):
        self.engine.reset_queue()
        self.engine.resolve_dependencies("bundle-meta")
        self.assertIn("base-core:service.sh", self.engine.files_to_deploy)
        self.assertIn("worker-service:worker.sh", self.engine.files_to_deploy)


class TestDeployEngine2Features(unittest.TestCase):
    """Тесты обхода дерева папок, пустых манифестов и установщика директорий."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_folder_hierarchy_and_empty_manifests(self):
        """
        Проверка логики обхода:
        - Вложенные папки с manifest.json (в т.ч. пустым {} и только с desc) обходятся рекурсивно.
        - Папки без manifest.json игнорируются.
        """
        cat_dir = os.path.join(self.test_dir, "services")
        empty_dir = os.path.join(self.test_dir, "services", "empty-group")
        pkg_dir = os.path.join(self.test_dir, "services", "server")
        ignored_dir = os.path.join(pkg_dir, "files")
        no_manifest_branch = os.path.join(self.test_dir, "untracked", "deep")

        os.makedirs(empty_dir, exist_ok=True)
        os.makedirs(ignored_dir, exist_ok=True)
        os.makedirs(no_manifest_branch, exist_ok=True)

        # Манифест папки только с desc
        with open(os.path.join(cat_dir, "manifest.json"), "w") as f:
            f.write('{"desc": "Сетевые и системные сервисы"}')

        # Полностью пустой манифест в папке
        with open(os.path.join(empty_dir, "manifest.json"), "w") as f:
            f.write("{}")

        # Манифест пакета во вложенной папке
        with open(os.path.join(pkg_dir, "manifest.json"), "w") as f:
            f.write('{"name": "server", "desc": "Сервис обработки"}')

        # Манифест внутри ветки без родительского manifest.json (должен быть проигнорирован)
        with open(os.path.join(no_manifest_branch, "manifest.json"), "w") as f:
            f.write('{"name": "hidden"}')

        registry = PackageRegistry(cache_file=os.path.join(self.test_dir, "cache.json"))
        registry.scan_directories([self.test_dir], force_rescan=True)

        self.assertIn("services", registry.folders)
        self.assertEqual(registry.folders["services"]["desc"], "Сетевые и системные сервисы")
        self.assertIn("services/empty-group", registry.folders)
        self.assertTrue(registry.has("server"))
        self.assertFalse(registry.has("hidden"))
        self.assertEqual(registry.get("server")["folder_path"], "services")

    def test_directory_unit_install_and_reinstall(self):
        """Проверка установки и повторной перезаписи директории files без ошибки [Errno 21] Is a directory."""
        src_files_dir = os.path.join(self.test_dir, "src_pkg", "files")
        os.makedirs(src_files_dir, exist_ok=True)
        with open(os.path.join(src_files_dir, "main.py"), "w") as f:
            f.write("print('v1')\n")

        dest_files_dir = os.path.join(self.test_dir, "opt_de_pkg", "files")
        txn = TransactionManager()
        installer = FileInstaller(ExecutionContext(), txn)

        # Первая установка директории
        installer.install_file(src_files_dir, dest_files_dir, 0o755, "file")
        txn.commit()
        self.assertTrue(os.path.isdir(dest_files_dir))

        # Повторная установка поверх существующей директории (ранее вызывала Errno 21)
        with open(os.path.join(src_files_dir, "main.py"), "w") as f:
            f.write("print('v2')\n")
        installer.install_file(src_files_dir, dest_files_dir, 0o755, "file")
        txn.commit()
        with open(os.path.join(dest_files_dir, "main.py")) as f:
            self.assertIn("v2", f.read())

    def test_name_collision_resolver(self):
        resolver = NameCollisionResolver()
        resolver.register_package("backend/api", "api")
        resolver.register_package("frontend/api", "api")
        resolver.register_package("system/core", "core")

        self.assertEqual(resolver.resolve("core"), "system/core")
        self.assertEqual(resolver.resolve("backend/api"), "backend/api")
        with self.assertRaises(NameCollisionError):
            resolver.resolve("api")

    def test_dependency_graph_and_cycle_detection(self):
        registry = PackageRegistry()
        registry.register({"name": "pkg-c", "requires": [], "units": {}})
        registry.register({"name": "pkg-b", "requires": ["pkg-c"], "units": {}})
        registry.register({"name": "pkg-a", "requires": ["pkg-b"], "units": {}})

        graph = DependencyGraph(registry)
        self.assertEqual(graph.resolve_order(["pkg-a"]), ["pkg-c", "pkg-b", "pkg-a"])

        cycle_reg = PackageRegistry()
        cycle_reg.register({"name": "cycle-a", "requires": ["cycle-b"], "units": {}})
        cycle_reg.register({"name": "cycle-b", "requires": ["cycle-a"], "units": {}})
        with self.assertRaises(DependencyCycleError):
            DependencyGraph(cycle_reg).resolve_order(["cycle-a"])

    def test_non_destructive_env_upsert_and_clean_env(self):
        dest_env = os.path.join(self.test_dir, "test.env")
        src_env = os.path.join(self.test_dir, "template.env")
        with open(dest_env, "w") as f:
            f.write("DB_USER=my_custom_user\n")
        with open(src_env, "w") as f:
            f.write("DB_USER=default_user\nDB_PORT=5432\n")

        EnvUpsertManager(ExecutionContext(clean_env=False), TransactionManager()).upsert_env_file(src_env, dest_env)
        with open(dest_env) as f:
            content = f.read()
        self.assertIn("DB_USER=my_custom_user", content)
        self.assertIn("DB_PORT=5432", content)

        EnvUpsertManager(ExecutionContext(clean_env=True), TransactionManager()).upsert_env_file(src_env, dest_env)
        with open(dest_env) as f:
            self.assertIn("DB_USER=default_user", f.read())

    def test_data_unit_and_transaction_rollback(self):
        dest_data = os.path.join(self.test_dir, "db.sqlite")
        src_data = os.path.join(self.test_dir, "seed.sqlite")
        with open(dest_data, "w") as f:
            f.write("PRODUCTION_USER_DATA")
        with open(src_data, "w") as f:
            f.write("SEED_DATA")

        DataUnitInstaller(ExecutionContext(), TransactionManager()).install_data_unit(src_data, dest_data)
        with open(dest_data) as f:
            self.assertEqual(f.read(), "PRODUCTION_USER_DATA")


if __name__ == "__main__":
    unittest.main()
