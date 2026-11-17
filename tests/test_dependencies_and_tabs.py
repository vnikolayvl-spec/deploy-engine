"""
Модульные тесты пропуска уже установленных зависимостей (при install и reinstall)
и раздельной индикации статуса .env (❗/🔧/🔒) и завершения установки (✅) на вкладках ExecutionModal.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files"))

from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext


class TestDependenciesAndTabs(unittest.TestCase):
    """Тестирование пропуска установленных зависимостей и индикации вкладок в модальном окне TUI."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_deps_tabs_test_")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        self.sb_dir = os.path.join(self.test_dir, "sandbox")
        os.makedirs(self.repo_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_dep_and_app_packages(self) -> None:
        dep_dir = os.path.join(self.repo_dir, "core", "setup-certs")
        app_dir = os.path.join(self.repo_dir, "core", "setup-dyndns")
        os.makedirs(dep_dir, exist_ok=True)
        os.makedirs(app_dir, exist_ok=True)

        with open(os.path.join(dep_dir, "deploy.env"), "w", encoding="utf-8") as f:
            f.write('CERTBOT_DOMAINS="skip"\n')
        with open(os.path.join(dep_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": "setup-certs",
                    "version": "2.0.0",
                    "desc": "Сертификаты",
                    "units": {"deploy.env": {"type": "env", "desc": "Конфиг сертификатов"}},
                },
                f,
            )

        with open(os.path.join(app_dir, "deploy.env"), "w", encoding="utf-8") as f:
            f.write('DYNDNS_ENABLED="false"\n')
        with open(os.path.join(app_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": "setup-dyndns",
                    "version": "2.0.0",
                    "desc": "DynDNS клиент",
                    "requires": ["setup-certs"],
                    "units": {"deploy.env": {"type": "env", "desc": "Конфиг DynDNS"}},
                },
                f,
            )

    def test_skip_already_installed_dependencies_on_install_and_reinstall(self):
        """
        Проверяет, что:
        1) если зависимость setup-certs еще не установлена — она устанавливается вместе с setup-dyndns;
        2) если setup-certs уже установлена — при install или reinstall setup-dyndns зависимость setup-certs пропускается;
        3) если setup-certs указана в targets явно — она устанавливается/переустанавливается.
        """
        self._create_dep_and_app_packages()
        ctx = ExecutionContext(sandbox=True, sandbox_os="debian", sandbox_dir=self.sb_dir, non_interactive=True)
        engine = Engine(ctx)
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)

        # 1. Когда ничего не установлено: порядок включает и setup-certs, и setup-dyndns
        order_initial, skipped_initial = engine.dep_graph.resolve_install_order(
            ["setup-dyndns"], is_installed_fn=engine.state_repo.get_installed_package
        )
        self.assertEqual(order_initial, ["core/setup-certs", "core/setup-dyndns"])
        self.assertEqual(skipped_initial, [])

        # Устанавливаем сначала только зависимость setup-certs
        engine.install_packages(["setup-certs"])
        self.assertIsNotNone(engine.state_repo.get_installed_package("setup-certs"))

        # 2. Теперь устанавливаем setup-dyndns: setup-certs должна быть пропущена!
        status_events = []
        ctx.add_pkg_status_listener(lambda pkg, st: status_events.append((pkg, st)))
        engine.install_packages(["setup-dyndns"])
        self.assertEqual(status_events, [("setup-dyndns", "running"), ("setup-dyndns", "done")])

        # 3. При переустановке (reinstall) setup-dyndns зависимость setup-certs также пропускается
        status_events.clear()
        engine.reinstall_package("setup-dyndns")
        # В событиях только uninstall и install для setup-dyndns, без setup-certs
        self.assertEqual(
            status_events,
            [
                ("setup-dyndns", "running"),
                ("setup-dyndns", "done"),
                ("setup-dyndns", "running"),
                ("setup-dyndns", "done"),
            ],
        )

    def test_execution_modal_separate_env_and_completion_badges(self):
        """
        Проверяет, что на вкладках ExecutionModal:
        - уже установленные зависимости не создают лишних вкладок;
        - статус принятого .env отображается значком 🔒 (а до принятия 🔧 или ❗);
        - галочка ✅ ставится на вкладке только после завершения установки пакета (status == 'done').
        """
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

        from lib.ui.execution_modal import ExecutionModal

        self._create_dep_and_app_packages()
        ctx = ExecutionContext(sandbox=True, sandbox_os="debian", sandbox_dir=self.sb_dir, non_interactive=True)
        engine = Engine(ctx)
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)

        # Когда оба пакета еще не установлены — создаются 2 вкладки
        modal_both = ExecutionModal(engine, {"setup-dyndns": "install"})
        self.assertEqual(modal_both.ordered_pkg_names, ["setup-certs", "setup-dyndns"])

        # Устанавливаем setup-certs: теперь в модальном окне для setup-dyndns должна быть только 1 вкладка
        engine.install_packages(["setup-certs"])
        modal = ExecutionModal(engine, {"setup-dyndns": "install"})
        self.assertEqual(modal.ordered_pkg_names, ["setup-dyndns"])

        # Симулируем смонтированное окно и проверяем смену значков вкладки
        fake_tab_btn = SimpleNamespace(label="")
        fake_log = SimpleNamespace(display=False)
        fake_panel = SimpleNamespace(approved=False, locked=False, has_missing_required_now=lambda: False)
        modal.env_panels["setup-dyndns"] = fake_panel

        def _fake_query_one(selector, *_args):
            if selector == "#tab_btn_setup-dyndns":
                return fake_tab_btn
            if selector == "#exec_log_setup-dyndns":
                return fake_log
            return SimpleNamespace(label="", variant="default", display=True, update=lambda *_a: None)

        modal.query_one = _fake_query_one
        type(modal).is_mounted = property(lambda _self: True)

        # 1. До принятия .env и до начала установки: 📦 setup-dyndns 🔧
        modal._refresh_pkg_tab_label("setup-dyndns")
        self.assertEqual(fake_tab_btn.label, "📦 setup-dyndns 🔧")

        # 2. После нажатия «Принять .env», пока пакет еще не завершил установку: 📦 setup-dyndns 🔒 (без галочки ✅!)
        fake_panel.approved = True
        modal._refresh_pkg_tab_label("setup-dyndns")
        self.assertEqual(fake_tab_btn.label, "📦 setup-dyndns 🔒")

        # 3. Во время выполнения пакета: ⏳ setup-dyndns 🔒
        modal.pkg_exec_status["setup-dyndns"] = "running"
        modal._refresh_pkg_tab_label("setup-dyndns")
        self.assertEqual(fake_tab_btn.label, "⏳ setup-dyndns 🔒")

        # 4. После завершения установки пакета: ✅ setup-dyndns 🔒
        modal.pkg_exec_status["setup-dyndns"] = "done"
        modal._refresh_pkg_tab_label("setup-dyndns")
        self.assertEqual(fake_tab_btn.label, "✅ setup-dyndns 🔒")

    def test_all_deploy_engine_files_under_300_lines_and_no_ufe0f(self):
        """Проверяет, что все .py файлы в deploy-engine не превышают 300 строк и не содержат U+FE0F."""
        engine_root = Path(__file__).resolve().parent.parent
        fe0f = chr(0xFE0F)
        for py_file in engine_root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            text = py_file.read_text(encoding="utf-8")
            lines = text.splitlines()
            self.assertLessEqual(len(lines), 300, f"{py_file} превышает 300 строк ({len(lines)})")
            self.assertNotIn(fe0f, text, f"Обнаружен символ U+FE0F в {py_file}")


if __name__ == "__main__":
    unittest.main()
