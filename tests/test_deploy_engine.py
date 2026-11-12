import json
import os
import shutil
import tempfile
import unittest

from lib.core.dependency_cycle_error import DependencyCycleError
from lib.core.execution_context import ExecutionContext
from lib.core.name_collision_error import NameCollisionError
from lib.dependencies.dependency_graph import DependencyGraph
from lib.discovery.category_manifest_parser import CategoryManifestParser
from lib.discovery.name_collision_resolver import NameCollisionResolver
from lib.discovery.package_registry import PackageRegistry
from lib.engine import Engine
from lib.env.env_upsert_manager import EnvUpsertManager
from lib.installer.data_unit_installer import DataUnitInstaller
from lib.installer.file_installer import FileInstaller
from lib.installer.transaction_manager import TransactionManager


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
    """Тесты разделения манифестов подкатегорий и пакетов, активности и установщика директорий."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_category_and_package_manifests_separation(self):
        """
        Проверка строгого разделения category.json (для категорий) и manifest.json (для пакетов),
        а также автоматического построения вложенных категорий без category.json по иерархии папок.
        """
        active_cat = os.path.join(self.test_dir, "services")
        inactive_cat = os.path.join(self.test_dir, "experimental")
        empty_cat = os.path.join(self.test_dir, "services", "empty-group")
        pkg_dir = os.path.join(self.test_dir, "services", "server")
        inactive_pkg_dir = os.path.join(self.test_dir, "experimental", "beta-node")
        nested_no_cat_pkg_dir = os.path.join(self.test_dir, "network", "vpn", "wireguard")

        os.makedirs(empty_cat, exist_ok=True)
        os.makedirs(pkg_dir, exist_ok=True)
        os.makedirs(inactive_pkg_dir, exist_ok=True)
        os.makedirs(nested_no_cat_pkg_dir, exist_ok=True)

        # Манифест активной категории с кастомным заголовком title, описанием и порядком
        with open(os.path.join(active_cat, "category.json"), "w") as f:
            json.dump({"title": "Core Services", "desc": "Основные сервисы", "active": True, "order": 10}, f)

        # Манифест неактивной категории (active: false) строго через category.json
        with open(os.path.join(inactive_cat, "category.json"), "w") as f:
            json.dump({"desc": "Экспериментальные модули", "active": False}, f)

        # Пустой category.json подкатегории
        with open(os.path.join(empty_cat, "category.json"), "w") as f:
            f.write("{}")

        # Манифест пакета в активной категории
        with open(os.path.join(pkg_dir, "manifest.json"), "w") as f:
            json.dump({"name": "server", "desc": "Сервис обработки", "units": {"app.sh": {"type": "script"}}}, f)

        # Манифест пакета в неактивной категории
        with open(os.path.join(inactive_pkg_dir, "manifest.json"), "w") as f:
            json.dump({"name": "beta-node", "desc": "Бета узел"}, f)

        # Пакет во вложенных папках network/vpn/ без category.json (должны создаться автоматически по имени папки)
        with open(os.path.join(nested_no_cat_pkg_dir, "manifest.json"), "w") as f:
            json.dump({"name": "wireguard", "desc": "VPN туннель"}, f)

        registry = PackageRegistry(cache_file=os.path.join(self.test_dir, "cache.json"))
        registry.scan_directories([self.test_dir], force_rescan=True)

        self.assertIn("services", registry.folders)
        self.assertEqual(registry.folders["services"]["title"], "Core Services")
        self.assertEqual(registry.folders["services"]["desc"], "Основные сервисы")
        self.assertTrue(registry.folders["services"]["active"])
        self.assertTrue(registry.is_folder_active("services"))

        self.assertIn("experimental", registry.folders)
        self.assertFalse(registry.folders["experimental"]["active"])
        self.assertFalse(registry.is_folder_active("experimental"))
        self.assertFalse(registry.get("beta-node")["active"])

        self.assertIn("services/empty-group", registry.folders)
        self.assertIn("network", registry.folders)
        self.assertIn("network/vpn", registry.folders)
        self.assertEqual(registry.folders["network/vpn"]["name"], "vpn")
        self.assertTrue(registry.has("wireguard"))
        self.assertEqual(registry.get("wireguard")["folder_path"], "network/vpn")
        self.assertEqual(registry.get("server")["folder_path"], "services")

    def test_category_manifest_parser_direct(self):
        """Проверка парсинга атрибутов подкатегории (active, desc, order, meta)."""
        parser = CategoryManifestParser()
        norm = parser.normalize_category(
            {"desc": "Тестовая категория", "active": "false", "order": 5, "meta": {"tag": "core"}},
            "/tmp/net-cat",
        )
        self.assertTrue(norm["is_category"])
        self.assertEqual(norm["name"], "net-cat")
        self.assertEqual(norm["desc"], "Тестовая категория")
        self.assertFalse(norm["active"])
        self.assertEqual(norm["order"], 5)
        self.assertEqual(norm["meta"]["tag"], "core")

    def test_directory_unit_install_and_reinstall(self):
        """Проверка установки и повторной перезаписи директории files без ошибки [Errno 21] Is a directory."""
        src_files_dir = os.path.join(self.test_dir, "src_pkg", "files")
        os.makedirs(src_files_dir, exist_ok=True)
        with open(os.path.join(src_files_dir, "main.py"), "w") as f:
            f.write("print('v1')\n")

        dest_files_dir = os.path.join(self.test_dir, "opt_de_pkg", "files")
        txn = TransactionManager()
        installer = FileInstaller(ExecutionContext(), txn)

        installer.install_file(src_files_dir, dest_files_dir, 0o755, "file")
        txn.commit()
        self.assertTrue(os.path.isdir(dest_files_dir))

        with open(os.path.join(src_files_dir, "main.py"), "w") as f:
            f.write("print('v2')\n")
        installer.install_file(src_files_dir, dest_files_dir, 0o755, "file")
        txn.commit()
        with open(os.path.join(dest_files_dir, "main.py")) as f:
            self.assertIn("v2", f.read())

    def test_name_collision_and_dependency_graph(self):
        resolver = NameCollisionResolver()
        resolver.register_package("backend/api", "api")
        resolver.register_package("frontend/api", "api")
        with self.assertRaises(NameCollisionError):
            resolver.resolve("api")

        registry = PackageRegistry()
        registry.register({"name": "pkg-b", "requires": [], "units": {}})
        registry.register({"name": "pkg-a", "requires": ["pkg-b"], "units": {}})
        self.assertEqual(DependencyGraph(registry).resolve_order(["pkg-a"]), ["pkg-b", "pkg-a"])

        cycle_reg = PackageRegistry()
        cycle_reg.register({"name": "cycle-a", "requires": ["cycle-b"], "units": {}})
        cycle_reg.register({"name": "cycle-b", "requires": ["cycle-a"], "units": {}})
        with self.assertRaises(DependencyCycleError):
            DependencyGraph(cycle_reg).resolve_order(["cycle-a"])

    def test_env_upsert_and_data_unit(self):
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

        dest_data = os.path.join(self.test_dir, "db.sqlite")
        src_data = os.path.join(self.test_dir, "seed.sqlite")
        with open(dest_data, "w") as f:
            f.write("PRODUCTION_USER_DATA")
        with open(src_data, "w") as f:
            f.write("SEED_DATA")
        DataUnitInstaller(ExecutionContext(), TransactionManager()).install_data_unit(src_data, dest_data)
        with open(dest_data) as f:
            self.assertEqual(f.read(), "PRODUCTION_USER_DATA")

    def test_infer_targets_and_folder_without_manifest_source(self):
        """Проверка автоопределения пакета из манифеста и сканирования папки без корневого манифеста."""
        root_without_manifest = os.path.join(self.test_dir, "packages_source")
        pkg_alpha_dir = os.path.join(root_without_manifest, "alpha-pkg")
        pkg_multi_dir = os.path.join(root_without_manifest, "multi-pkg")
        os.makedirs(pkg_alpha_dir, exist_ok=True)
        os.makedirs(pkg_multi_dir, exist_ok=True)

        alpha_manifest = os.path.join(pkg_alpha_dir, "manifest.json")
        with open(alpha_manifest, "w") as f:
            json.dump({"name": "alpha-pkg", "desc": "Пакет Альфа", "units": {}}, f)

        multi_manifest = os.path.join(pkg_multi_dir, "manifest.json")
        with open(multi_manifest, "w") as f:
            json.dump({"packages": {"multi-pkg": {"desc": "Основной"}, "multi": {"requires": ["multi-pkg"]}}, "units": {}}, f)

        engine = Engine()
        # 1. Источник дерева пакетов — папка без манифеста в корне
        found = engine.load_manifest_recursive(root_without_manifest)
        self.assertGreaterEqual(found, 2)
        self.assertTrue(engine.registry.has("alpha-pkg"))
        self.assertTrue(engine.registry.has("multi-pkg"))

        # 2. Автоопределение целевого пакета по пути к манифесту (исключая алиасы)
        self.assertEqual(engine.infer_targets_from_manifest(alpha_manifest), ["alpha-pkg"])
        self.assertEqual(engine.infer_targets_from_manifest(multi_manifest), ["multi-pkg"])


if __name__ == "__main__":
    unittest.main()
