"""
Unit tests for BackupManager and Engine backup/restore commands:
- Multiple data and env units with custom predefined dest paths
- Multiple backups per package with --comment
- Restore latest [1] by default and restore specific backup by index or timestamp
- Meta-target 'all' for backup and restore
- Path Traversal (Tar Slip) protection
"""
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files"))

from lib.core.deploy_engine_error import DeployEngineError
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext


class TestBackupAndRestore(unittest.TestCase):
    """Тестирование резервного копирования (backup) и восстановления (restore) данных и окружения пакетов."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_backup_test_")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        self.sb_dir = os.path.join(self.test_dir, "sandbox")
        self.backup_dir = os.path.join(self.test_dir, "backups")
        os.makedirs(self.repo_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_multi_path_package(self, pkg_name: str = "billing-svc") -> str:
        pkg_dir = os.path.join(self.repo_dir, pkg_name)
        os.makedirs(pkg_dir, exist_ok=True)

        with open(os.path.join(pkg_dir, "deploy.env"), "w", encoding="utf-8") as f:
            f.write("DB_MODE=prod\nAPI_SECRET=v1_secret\n")
        with open(os.path.join(pkg_dir, "extra.env"), "w", encoding="utf-8") as f:
            f.write("EXTRA_TOKEN=token_v1\n")
        with open(os.path.join(pkg_dir, "main.sqlite"), "w", encoding="utf-8") as f:
            f.write("MAIN_DB_V1")
        with open(os.path.join(pkg_dir, "analytics.db"), "w", encoding="utf-8") as f:
            f.write("ANALYTICS_V1")

        manifest = {
            "name": pkg_name,
            "version": "1.2.0",
            "desc": "Сервис биллинга с несколькими БД и .env",
            "units": {
                "deploy.env": {"type": "env", "desc": "Основной конфиг"},
                "extra.env": {
                    "type": "env",
                    "dest": f"/etc/custom_{pkg_name}/extra.env",
                    "desc": "Дополнительный env с кастомным путем",
                },
                "main.sqlite": {"type": "data", "desc": "Основная база в /var/lib/de_*"},
                "analytics.db": {
                    "type": "data",
                    "dest": f"/srv/{pkg_name}_data/analytics.db",
                    "desc": "Вторая БД по предопределенному пути",
                },
            },
        }
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        return pkg_dir

    def test_multi_backup_with_custom_paths_comments_and_selective_restore(self):
        """
        Проверка создания нескольких бэкапов одного пакета с несколькими путями data и env
        (включая кастомные dest), комментариями --comment, выбора по умолчанию [1] и по индексу [2].
        """
        self._create_multi_path_package("billing-svc")
        ctx = ExecutionContext(sandbox=True, sandbox_os="debian", sandbox_dir=self.sb_dir, non_interactive=True)
        engine = Engine(ctx)
        engine.backup_manager.backup_root_dir = self.backup_dir
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)
        engine.install_packages(["billing-svc"])

        std_env = os.path.join(self.sb_dir, "etc", "default", "de_billing-svc", "billing-svc.env")
        custom_env = os.path.join(self.sb_dir, "etc", "custom_billing-svc", "extra.env")
        std_db = os.path.join(self.sb_dir, "var", "lib", "de_billing-svc", "main.sqlite")
        custom_db = os.path.join(self.sb_dir, "srv", "billing-svc_data", "analytics.db")

        # 1. Создаем Бэкап №1 (v1 состояние)
        res1 = engine.backup_packages(["billing-svc"], comment="Слепок v1 до миграции")[0]
        self.assertTrue(os.path.isfile(res1["archive_path"]))
        self.assertEqual(res1["comment"], "Слепок v1 до миграции")
        self.assertEqual(len(res1["items"]), 4)

        # Модифицируем обе БД и оба .env (состояние v2)
        with open(std_db, "w", encoding="utf-8") as f:
            f.write("MAIN_DB_V2_UPDATED")
        with open(custom_db, "w", encoding="utf-8") as f:
            f.write("ANALYTICS_V2_UPDATED")
        with open(std_env, "w", encoding="utf-8") as f:
            f.write("DB_MODE=staging\nAPI_SECRET=v2_secret\n")
        with open(custom_env, "w", encoding="utf-8") as f:
            f.write("EXTRA_TOKEN=token_v2\n")

        # 2. Создаем Бэкап №2 (свежий, состояние v2)
        res2 = engine.backup_packages(["billing-svc"], comment="Слепок v2 после миграции")[0]
        self.assertNotEqual(res1["archive_path"], res2["archive_path"])

        backups_list = engine.backup_manager.list_package_backups("billing-svc")
        self.assertEqual(len(backups_list), 2)
        self.assertTrue(backups_list[0]["is_latest"])
        self.assertEqual(backups_list[0]["comment"], "Слепок v2 после миграции")
        self.assertEqual(backups_list[1]["comment"], "Слепок v1 до миграции")

        list_text = engine.backup_manager.format_backups_list(["billing-svc"])
        self.assertIn("Слепок v2 после миграции", list_text)
        self.assertIn("/srv/billing-svc_data/analytics.db", list_text)
        self.assertIn("/etc/custom_billing-svc/extra.env", list_text)

        # Портим файлы на диске (состояние corrupted)
        for p in (std_db, custom_db, std_env, custom_env):
            with open(p, "w", encoding="utf-8") as f:
                f.write("CORRUPTED")

        # 3. Восстановление по умолчанию (без селектора) должно откатить к самому свежему бэкапу [1] (v2)
        engine.restore_packages(["billing-svc"])
        self.assertEqual(open(std_db, encoding="utf-8").read(), "MAIN_DB_V2_UPDATED")
        self.assertEqual(open(custom_db, encoding="utf-8").read(), "ANALYTICS_V2_UPDATED")
        self.assertIn("API_SECRET=v2_secret", open(std_env, encoding="utf-8").read())
        self.assertIn("EXTRA_TOKEN=token_v2", open(custom_env, encoding="utf-8").read())

        # 4. Восстановление по индексу "2" должно откатить ко второму в списке (более раннему v1) бэкапу
        engine.restore_packages(["billing-svc"], selector="2")
        self.assertEqual(open(std_db, encoding="utf-8").read(), "MAIN_DB_V1")
        self.assertEqual(open(custom_db, encoding="utf-8").read(), "ANALYTICS_V1")
        self.assertIn("API_SECRET=v1_secret", open(std_env, encoding="utf-8").read())
        self.assertIn("EXTRA_TOKEN=token_v1", open(custom_env, encoding="utf-8").read())

    def test_meta_target_all_and_path_traversal_protection(self):
        """Проверка мета-значения 'all' для backup/restore и блокировки Path Traversal при распаковке."""
        self._create_multi_path_package("app-one")
        self._create_multi_path_package("app-two")

        ctx = ExecutionContext(sandbox=True, sandbox_os="debian", sandbox_dir=self.sb_dir, non_interactive=True)
        engine = Engine(ctx)
        engine.backup_manager.backup_root_dir = self.backup_dir
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)
        engine.install_packages(["app-one", "app-two"])

        # Бэкап всех установленных пакетов через 'all'
        results = engine.backup_packages(["all"], comment="Массовый бэкап")
        self.assertEqual(len(results), 2)

        # Удаляем данные обоих пакетов и восстанавливаем через 'all'
        db_one = os.path.join(self.sb_dir, "var", "lib", "de_app-one", "main.sqlite")
        db_two = os.path.join(self.sb_dir, "var", "lib", "de_app-two", "main.sqlite")
        os.unlink(db_one)
        os.unlink(db_two)

        engine.restore_packages(["all"])
        self.assertTrue(os.path.isfile(db_one))
        self.assertTrue(os.path.isfile(db_two))

        # Проверка защиты от Path Traversal (Tar Slip)
        evil_dir = os.path.join(self.backup_dir, "app-one")
        evil_tar_path = os.path.join(evil_dir, "20991231_235959.tar.gz")
        with tarfile.open(evil_tar_path, "w:gz") as tar:
            evil_data = b"pwned"
            ti = tarfile.TarInfo(name="../../etc/passwd")
            ti.size = len(evil_data)
            tar.addfile(ti, io.BytesIO(evil_data))

        with self.assertRaises(DeployEngineError):
            engine.restore_packages(["app-one"], selector="20991231_235959")


if __name__ == "__main__":
    unittest.main()
