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
            "name": pkg_name, "version": "1.2.0", "desc": "Сервис биллинга с несколькими БД и .env",
            "units": {
                "deploy.env": {"type": "env", "desc": "Основной конфиг"},
                "extra.env": {"type": "env", "dest": f"/etc/custom_{pkg_name}/extra.env", "desc": "Дополнительный env с кастомным путем"},
                "main.sqlite": {"type": "data", "desc": "Основная база в /var/lib/de_*"},
                "analytics.db": {"type": "data", "dest": f"/srv/{pkg_name}_data/analytics.db", "desc": "Вторая БД по предопределенному пути"},
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

    def test_tui_backup_restore_plan_order_and_double_q_exit(self):
        """
        Проверка TUI-плана:
        1) быстрый подсчет count_package_backups без распаковки архивов;
        2) при одновременном выборе бэкапа и восстановления сначала создается бэкап, затем выполняется восстановление;
        3) выход по двойному нажатию q-q в течение 1 секунды (одиночное q только показывает подсказку).
        """
        from types import ModuleType, SimpleNamespace
        from unittest.mock import patch
        import main as main_mod

        try:
            import textual  # noqa: F401
        except ImportError:
            class _Meta(type):
                def __getattr__(cls, _name):
                    return object

            class _DummyWidget(metaclass=_Meta):
                def __init__(self, *a, **kw):
                    self.focused = None

            for mod_name, attrs in {
                "textual": {},
                "textual.app": {"App": _DummyWidget, "ComposeResult": object},
                "textual.containers": {"Horizontal": _DummyWidget, "Vertical": _DummyWidget, "VerticalScroll": _DummyWidget},
                "textual.screen": {"ModalScreen": _DummyWidget},
                "textual.widgets": {
                    "Button": _DummyWidget, "Checkbox": _DummyWidget, "Footer": _DummyWidget, "Header": _DummyWidget,
                    "Input": _DummyWidget, "Label": _DummyWidget, "OptionList": _DummyWidget, "RichLog": _DummyWidget,
                    "Select": _DummyWidget, "Tree": _DummyWidget,
                },
                "textual.widgets.option_list": {"Option": _DummyWidget},
                "textual.widgets.tree": {"TreeNode": _DummyWidget},
            }.items():
                m = ModuleType(mod_name)
                for k, v in attrs.items():
                    setattr(m, k, v)
                sys.modules[mod_name] = m

        from lib.ui_app import DeployApp

        self._create_multi_path_package("billing-svc")
        ctx = ExecutionContext(sandbox=True, sandbox_os="debian", sandbox_dir=self.sb_dir, non_interactive=True)
        engine = Engine(ctx)
        engine.backup_manager.backup_root_dir = self.backup_dir
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)
        engine.install_packages(["billing-svc"])

        self.assertEqual(engine.backup_manager.count_package_backups("billing-svc"), 0)
        b1 = engine.backup_packages(["billing-svc"], comment="Исходный v1")[0]
        self.assertEqual(engine.backup_manager.count_package_backups("billing-svc"), 1)

        std_db = os.path.join(self.sb_dir, "var", "lib", "de_billing-svc", "main.sqlite")
        with open(std_db, "w", encoding="utf-8") as f:
            f.write("STATE_BEFORE_RESTORE_V2")

        actions_plan = {
            "__backup__": ["billing-svc"],
            "__restore__": {"billing-svc": os.path.basename(b1["archive_path"])},
        }
        with patch.object(DeployApp, "run", return_value=actions_plan), patch("main.Engine", return_value=engine), patch("main.bootstrap_gui"):
            args = main_mod.build_parser().parse_args(["--tui", "--packages-dir", self.repo_dir])
            main_mod.run_tui(args, ctx)

        self.assertEqual(engine.backup_manager.count_package_backups("billing-svc"), 2)
        self.assertEqual(open(std_db, encoding="utf-8").read(), "MAIN_DB_V1")
        backups = engine.backup_manager.list_package_backups("billing-svc")
        self.assertEqual(len(backups), 2)

        app = DeployApp(engine)
        exited, notified = [], []
        app.exit = lambda *a, **kw: exited.append(True)
        app.notify = lambda msg, **kw: notified.append(msg)

        ev1 = SimpleNamespace(key="q", prevent_default=lambda: None, stop=lambda: None)
        app.on_key(ev1)
        self.assertEqual(len(exited), 0)
        self.assertEqual(len(notified), 1)

        app._last_q_time -= 2.0
        ev_ru_q = SimpleNamespace(key="й", character="й", prevent_default=lambda: None, stop=lambda: None)
        app.on_key(ev_ru_q)
        self.assertEqual(len(exited), 0)
        app.on_key(ev_ru_q)
        self.assertEqual(len(exited), 1)

        env_called = []
        app.action_edit_current_env = lambda: env_called.append(True)
        app.on_key(SimpleNamespace(key="у", character="у", prevent_default=lambda: None, stop=lambda: None))
        self.assertEqual(len(env_called), 1)

        # 4. Проверка install_DATE.log, сортировки левого списка, внешнего манифеста и удаленного манифеста
        from lib.state.package_inspector import PackageInspector
        from lib.ui.execution_modal import ExecutionModal

        second_dir = self._create_multi_path_package("second-svc")
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)
        ExecutionModal(engine, {"billing-svc": "reinstall"}).execute_plan_synchronously()
        st_entry = engine.state_repo.get_installed_package("billing-svc")
        self.assertTrue(os.path.isfile(st_entry.get("manifest_path", "")))

        inspector = PackageInspector(engine=engine)
        self.assertIn("Пакет: billing-svc | Операция: reinstall", inspector.get_latest_install_log("billing-svc"))

        # Загружаем только second-svc как целевой манифест: billing-svc должен подгрузиться как внешний (is_external_manifest=True)
        engine.load_manifest_recursive(os.path.join(second_dir, "manifest.json"))
        self.assertFalse(engine.registry.has("billing-svc"))
        dummy_opt_list = SimpleNamespace(clear_options=lambda: None, add_option=lambda _o: None, highlighted=0)
        app.query_one = lambda sel, *_a: dummy_opt_list
        app.actions = {"second-svc": "install"}
        app._last_tabs_sig = None
        app._sync_plan_tabs()
        self.assertEqual(app.option_pkg_map, [None, "second-svc", "billing-svc"])
        self.assertTrue(engine.registry.get("billing-svc").get("is_external_manifest"))

        # Если исходный манифест удален с диска — manifest_available=False
        os.unlink(st_entry["manifest_path"])
        engine.load_manifest_recursive(os.path.join(second_dir, "manifest.json"))
        app._last_tabs_sig = None
        app._sync_plan_tabs()
        self.assertFalse(inspector.get_package_info("billing-svc")["manifest_available"])


if __name__ == "__main__":
    unittest.main()

