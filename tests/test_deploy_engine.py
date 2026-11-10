import datetime
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
from lib.installer.transaction_manager import TransactionManager
from lib.state.package_inspector import PackageInspector
from lib.state.state_repository import StateRepository


class TestDeployEngineCore(unittest.TestCase):
    """Тесты ядра оркестрации с использованием абстрактных тестовых манифестов."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_core_test_")
        self.engine = Engine()

        # Создаем тестовую структуру абстрактных пакетов
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
                "deploy.env": {
                    "type": "env",
                    "desc": "Шаблон переменных окружения"
                },
                "service.sh": {
                    "type": "script",
                    "desc": "Системный исполняемый скрипт"
                },
                "files": {
                    "type": "file",
                    "desc": "Файлы приложения"
                },
                "worker.sh": {
                    "type": "script",
                    "desc": "Скрипт воркера"
                },
                "worker.service": {
                    "type": "unit",
                    "desc": "Служба systemd"
                }
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
        """Проверка свойства engine.units для совместимости с TUI (package_tree)."""
        units = self.engine.units
        self.assertIsInstance(units, dict)
        self.assertIn("service.sh", units)
        self.assertIn("worker.sh", units)
        self.assertIn("deploy.env", units)

    def test_load_default_manifests_alias(self):
        """Проверка метода load_default_manifests для TUI."""
        res = self.engine.load_default_manifests()
        self.assertIsInstance(res, int)

    def test_script_unit_path_resolution(self):
        self.engine.files_to_deploy.clear()
        self.engine.resolve_dependencies("base-core")
        self.assertIn("base-core:service.sh", self.engine.files_to_deploy)

        src, dest, mode, f_type = self.engine.get_paths_and_modes("base-core:service.sh")
        self.assertEqual(f_type, "script")
        self.assertEqual(mode, 0o755)
        self.assertTrue(dest.endswith("/usr/local/bin/service.sh"))

    def test_sys_packages_collection(self):
        self.engine.files_to_deploy.clear()
        self.engine.sys_packages_to_install.clear()
        self.engine.resolve_dependencies("base-core")

        sys_pkgs = self.engine.sys_packages_to_install
        self.assertIn("curl", sys_pkgs)
        self.assertIn("jq", sys_pkgs)
        self.assertIn("tmux", sys_pkgs)

    def test_dependency_chain_resolution(self):
        self.engine.files_to_deploy.clear()
        self.engine.resolve_dependencies("worker-service")
        # Должен подтянуть юниты base-core и затем worker-service
        self.assertIn("base-core:service.sh", self.engine.files_to_deploy)
        self.assertIn("worker-service:worker.service", self.engine.files_to_deploy)

    def test_meta_bundle_aggregation(self):
        self.engine.files_to_deploy.clear()
        self.engine.resolve_dependencies("bundle-meta")
        self.assertIn("base-core:service.sh", self.engine.files_to_deploy)
        self.assertIn("worker-service:worker.sh", self.engine.files_to_deploy)


class TestDeployEngine2Features(unittest.TestCase):
    """Новые возможности Deploy Engine 2.0 с абстрактными именами."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_directory_crawler_terminal_traversal(self):
        """Проверка: если найден manifest.json, обход подпапок пакета останавливается."""
        pkg_dir = os.path.join(self.test_dir, "services", "server")
        os.makedirs(os.path.join(pkg_dir, "subfolder"), exist_ok=True)

        with open(os.path.join(pkg_dir, "manifest.json"), "w") as f:
            f.write('{"name": "server", "version": "1.0.0"}')

        # Вложенный manifest внутри subfolder не должен читаться
        with open(os.path.join(pkg_dir, "subfolder", "manifest.json"), "w") as f:
            f.write('{"name": "ignored_nested"}')

        crawler = DirectoryCrawler([self.test_dir])
        found = crawler.crawl_all()

        self.assertIn("services/server", found)
        self.assertNotIn("services/server/subfolder", found, "Crawler must not descend into package subfolders")

    def test_name_collision_resolver(self):
        """Проверка разрешения одинаковых имен пакетов."""
        resolver = NameCollisionResolver()
        resolver.register_package("backend/api", "api")
        resolver.register_package("frontend/api", "api")
        resolver.register_package("system/core", "core")

        # Уникальное короткое имя
        self.assertEqual(resolver.resolve("core"), "system/core")

        # Прямое обращение по неймспейсу
        self.assertEqual(resolver.resolve("backend/api"), "backend/api")

        # Коллизия коротких имен
        with self.assertRaises(NameCollisionError) as ctx:
            resolver.resolve("api")
        self.assertEqual(ctx.exception.short_name, "api")
        self.assertIn("backend/api", ctx.exception.candidates)
        self.assertIn("frontend/api", ctx.exception.candidates)

    def test_package_cache_manager(self):
        """Проверка кэша packages.json."""
        cache_path = os.path.join(self.test_dir, "test_packages.json")
        cache = PackageCacheManager(cache_path)
        self.assertFalse(cache.has_cache())

        data = {"backend/server": {"name": "server", "version": "1.0.0"}}
        saved = cache.save_cache(data)
        self.assertTrue(saved)
        self.assertTrue(cache.has_cache())

        loaded = cache.load_cache()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["packages"]["backend/server"]["name"], "server")

    def test_dependency_graph_and_cycle_detection(self):
        """Проверка топологической сортировки Кана и обнаружения циклов."""
        registry = PackageRegistry()
        registry.register({"name": "pkg-c", "requires": [], "units": {}})
        registry.register({"name": "pkg-b", "requires": ["pkg-c"], "units": {}})
        registry.register({"name": "pkg-a", "requires": ["pkg-b"], "units": {}})

        graph = DependencyGraph(registry)
        order = graph.resolve_order(["pkg-a"])
        self.assertEqual(order, ["pkg-c", "pkg-b", "pkg-a"])

        # Проверка цикла A -> B -> A
        cycle_reg = PackageRegistry()
        cycle_reg.register({"name": "cycle-a", "requires": ["cycle-b"], "units": {}})
        cycle_reg.register({"name": "cycle-b", "requires": ["cycle-a"], "units": {}})
        cycle_graph = DependencyGraph(cycle_reg)

        with self.assertRaises(DependencyCycleError):
            cycle_graph.resolve_order(["cycle-a"])

    def test_non_destructive_env_upsert(self):
        """Проверка non-destructive upsert: существующие секреты не перезаписываются."""
        dest_env = os.path.join(self.test_dir, "test.env")
        src_env = os.path.join(self.test_dir, "template.env")

        # Создаем целевой env с пользовательским паролем
        with open(dest_env, "w") as f:
            f.write("DB_USER=my_custom_user\nDB_PASS=my_secret_password\n")

        # Шаблон содержит те же переменные и одну новую
        with open(src_env, "w") as f:
            f.write("DB_USER=default_user\nDB_PASS=default_pass\nDB_PORT=5432\n")

        context = ExecutionContext(clean_env=False)
        txn = TransactionManager()
        upsert_mgr = EnvUpsertManager(context, txn)

        upsert_mgr.upsert_env_file(src_env, dest_env)

        with open(dest_env, "r") as f:
            content = f.read()

        # Старые значения сохранены
        self.assertIn("DB_USER=my_custom_user", content)
        self.assertIn("DB_PASS=my_secret_password", content)
        # Новая переменная добавлена
        self.assertIn("DB_PORT=5432", content)
        # Дефолтные значения из шаблона НЕ затерли существующие
        self.assertNotIn("DB_USER=default_user", content)

    def test_clean_env_option(self):
        """Проверка флага clean_env: сброс к заводским настройкам шаблона."""
        dest_env = os.path.join(self.test_dir, "clean_test.env")
        src_env = os.path.join(self.test_dir, "clean_template.env")

        with open(dest_env, "w") as f:
            f.write("USER_VAL=old_val\n")

        with open(src_env, "w") as f:
            f.write("USER_VAL=factory_val\nNEW_KEY=123\n")

        context = ExecutionContext(clean_env=True)
        txn = TransactionManager()
        upsert_mgr = EnvUpsertManager(context, txn)

        upsert_mgr.upsert_env_file(src_env, dest_env)

        with open(dest_env, "r") as f:
            content = f.read()

        self.assertIn("USER_VAL=factory_val", content)
        self.assertNotIn("USER_VAL=old_val", content)

    def test_data_unit_installer_never_overwrites(self):
        """Проверка: юнит data никогда не перезаписывает существующие пользовательские файлы данных."""
        dest_data = os.path.join(self.test_dir, "db.sqlite")
        src_data = os.path.join(self.test_dir, "seed.sqlite")

        # Создаем существующую БД
        with open(dest_data, "w") as f:
            f.write("PRODUCTION_USER_DATA")

        # Шаблон содержит начальные пустые таблицы
        with open(src_data, "w") as f:
            f.write("SEED_DATA")

        context = ExecutionContext()
        txn = TransactionManager()
        installer = DataUnitInstaller(context, txn)

        installer.install_data_unit(src_data, dest_data)

        # Проверяем, что файл НЕ перезаписан
        with open(dest_data, "r") as f:
            content = f.read()
        self.assertEqual(content, "PRODUCTION_USER_DATA", "Existing database/data must never be overwritten!")

    def test_transaction_rollback_on_failure(self):
        """Проверка транзакционного отката (LIFO)."""
        txn = TransactionManager()
        f1 = os.path.join(self.test_dir, "file1.txt")
        f2 = os.path.join(self.test_dir, "file2.txt")

        # Создаем f1 и регистрируем
        with open(f1, "w") as f:
            f.write("f1")
        txn.record_created_file(f1)

        # Создаем f2 и регистрируем
        with open(f2, "w") as f:
            f.write("f2")
        txn.record_created_file(f2)

        self.assertTrue(os.path.exists(f1))
        self.assertTrue(os.path.exists(f2))

        # Вызываем откат
        txn.rollback()

        # Файлы должны быть удалены в ходе отката
        self.assertFalse(os.path.exists(f2))
        self.assertFalse(os.path.exists(f1))

    def test_package_inspector(self):
        """Проверка инспектора установленных пакетов."""
        state_file = os.path.join(self.test_dir, "test_state.json")
        repo = StateRepository(state_file_path=state_file)
        repo.mark_installed("pkg-demo", "2.1.0", ["/usr/local/bin/demo"], "system/pkg-demo")

        inspector = PackageInspector(state_repo=repo)
        installed = inspector.get_installed_list()

        self.assertEqual(len(installed), 1)
        self.assertEqual(installed[0]["package"], "pkg-demo")
        self.assertEqual(installed[0]["version"], "2.1.0")

        table = inspector.format_table()
        self.assertIn("pkg-demo", table)
        self.assertIn("2.1.0", table)

        json_out = inspector.to_json()
        self.assertIn('"pkg-demo"', json_out)

    def test_empty_manifest_is_valid(self):
        """Проверка: пустой файл manifest.json или {} в папке считается валидным."""
        empty_dir = os.path.join(self.test_dir, "empty_group")
        os.makedirs(empty_dir, exist_ok=True)
        manifest_file = os.path.join(empty_dir, "manifest.json")
        with open(manifest_file, "w", encoding="utf-8") as f:
            f.write("")

        from lib.discovery.manifest_parser import ManifestParser
        parser = ManifestParser()
        parsed = parser.parse_file(manifest_file)
        self.assertTrue(parsed.get("is_folder_only"))
        self.assertTrue(parsed.get("is_empty"))

    def test_folder_desc_from_nested_manifest(self):
        """Проверка: манифест во вложенной папке задает desc для этой папки."""
        group_dir = os.path.join(self.test_dir, "services_group")
        pkg_dir = os.path.join(group_dir, "app1")
        os.makedirs(pkg_dir, exist_ok=True)

        # Манифест группы папок
        with open(os.path.join(group_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"desc": "Группа микросервисов приложения"}, f)

        # Манифест пакета app1
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "app1", "desc": "Первый микросервис"}, f)

        registry = PackageRegistry()
        count = registry.scan_directories([self.test_dir], force_rescan=True)
        self.assertGreaterEqual(count, 1)

        desc = registry.get_folder_desc("services_group")
        self.assertEqual(desc, "Группа микросервисов приложения")

    def test_folders_without_manifest_are_ignored(self):
        """Проверка: папки, в которых нет manifest.json, игнорируются при обходе."""
        ignored_folder = os.path.join(self.test_dir, "unrelated_docs")
        os.makedirs(ignored_folder, exist_ok=True)
        with open(os.path.join(ignored_folder, "notes.txt"), "w") as f:
            f.write("Some notes")

        crawler = DirectoryCrawler([self.test_dir])
        found = crawler.crawl_all()
        for k in found.keys():
            self.assertNotIn("unrelated_docs", k)


if __name__ == "__main__":
    unittest.main()
