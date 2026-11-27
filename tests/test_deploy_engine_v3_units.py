"""
Тесты юнитов, инспектора, дерева TUI и сквозной интеграции Deploy Engine v3.0.0:
- нативный юнит web, точечное обновление <pkg>:<unit> / --only / --unit-type / --with-hooks;
- upgrade и version_history;
- EnvInspector (config --show + маскирование + самоинспекция deploy-engine);
- TreeStateKeeper (сохранение раскрытых веток и курсора);
- сквозная интеграция deploy-engine <-> de-lib <-> setup-notifier.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

DE_FILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files")
if DE_FILES_DIR not in sys.path:
    sys.path.insert(0, DE_FILES_DIR)

from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.env.env_inspector import EnvInspector
from lib.installer.selective_unit_runner import SelectiveUnitRunner
from lib.ui.tree_state_keeper import TreeStateKeeper


class TestDeployEngineV3Units(unittest.TestCase):
    """Тесты web-юнита, селективных обновлений, config --show, TUI-дерева и e2e-интеграции."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="de_v3_units_")
        self.sb_dir = os.path.join(self.tmp, "sandbox")
        self.env_dir = os.path.join(self.tmp, "local_env")
        os.makedirs(self.sb_dir, exist_ok=True)
        os.makedirs(self.env_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_sandbox_engine(self) -> Engine:
        ctx = ExecutionContext(sandbox=True, sandbox_os="debian", sandbox_dir=self.sb_dir, non_interactive=True)
        eng = Engine(ctx)
        eng.env_manager.local_env_dir = self.env_dir
        return eng

    def test_web_unit_selective_update_and_upgrade(self):
        pkg_dir = os.path.join(self.tmp, "repo", "demo-web")
        os.makedirs(os.path.join(pkg_dir, "web"), exist_ok=True)
        os.makedirs(os.path.join(pkg_dir, "files"), exist_ok=True)
        with open(os.path.join(pkg_dir, "web", "web.json"), "w", encoding="utf-8") as f:
            json.dump({"id": "demo-web", "title": "Demo"}, f)
        with open(os.path.join(pkg_dir, "web", "ui.js"), "w", encoding="utf-8") as f:
            f.write("console.log('v1');\n")
        with open(os.path.join(pkg_dir, "files", "app.py"), "w", encoding="utf-8") as f:
            f.write("print('v1')\n")
        hook_marker = os.path.join(self.tmp, "hook_ran.txt")
        manifest_path = os.path.join(pkg_dir, "manifest.json")
        manifest_data = {
            "name": "demo-web",
            "version": "1.0.0",
            "desc": "Тестовый веб-пакет",
            "post_install": [f"echo ran >> {hook_marker}"],
            "units": {"files": {"type": "file"}, "web": {"type": "web"}},
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)

        eng = self._make_sandbox_engine()
        eng.discover_packages([os.path.join(self.tmp, "repo")], force_rescan=True)
        _, web_dest, web_mode, web_type = eng.get_paths_and_modes("demo-web:web")
        self.assertEqual(web_type, "web")
        self.assertEqual(web_mode, 0o755)
        self.assertTrue(web_dest.endswith(os.path.join("de_demo-web", "web")))

        eng.install_packages(["demo-web"])
        self.assertTrue(os.path.isfile(os.path.join(web_dest, "ui.js")))

        with open(os.path.join(pkg_dir, "web", "ui.js"), "w", encoding="utf-8") as f:
            f.write("console.log('v2');\n")
        with open(os.path.join(pkg_dir, "files", "app.py"), "w", encoding="utf-8") as f:
            f.write("print('v2_untouched')\n")

        full_pkgs, u_map = SelectiveUnitRunner.split_targets_and_units(["demo-web:web"])
        self.assertEqual(full_pkgs, [])
        self.assertEqual(u_map, {"demo-web": ["web"]})

        eng.update_units("demo-web", unit_names=["web"], with_hooks=False)
        with open(os.path.join(web_dest, "ui.js"), encoding="utf-8") as fh:
            self.assertIn("v2", fh.read())
        files_dest = eng.get_paths_and_modes("demo-web:files")[1]
        with open(os.path.join(files_dest, "app.py"), encoding="utf-8") as fh:
            self.assertIn("v1", fh.read())

        manifest_data["version"] = "1.1.0"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f)
        eng.discover_packages([os.path.join(self.tmp, "repo")], force_rescan=True)
        upgraded = eng.upgrade_packages(["all"])
        self.assertEqual(len(upgraded), 1)
        self.assertEqual(upgraded[0]["available_version"], "1.1.0")
        state = eng.state_repo.get_installed_package("demo-web")
        self.assertEqual(state["version"], "1.1.0")
        self.assertGreaterEqual(len(state.get("version_history", [])), 2)

    def test_config_show_inspector_and_masking(self):
        pkg_dir = os.path.join(self.tmp, "repo", "cfg-demo")
        os.makedirs(pkg_dir, exist_ok=True)
        with open(os.path.join(pkg_dir, "deploy.env"), "w", encoding="utf-8") as f:
            f.write('SERVER_NAME="#AUTO#"\nAPI_SECRET="supersecretvalue123"\nOPT_KEY="#SKIP#"\n')
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "cfg-demo", "version": "1.0.0", "units": {"deploy.env": {"type": "env"}}}, f)

        eng = self._make_sandbox_engine()
        eng.discover_packages([os.path.join(self.tmp, "repo")], force_rescan=True)
        eng.install_packages(["cfg-demo"])

        def fake_runner(cmd, **_kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({
                    "package": "cfg-demo",
                    "entries": {
                        "SERVER_NAME": {"raw": "#AUTO#", "resolved": "node-alpha", "source": "auto", "secret": False},
                        "API_SECRET": {"raw": "supersecretvalue123", "resolved": "supersecretvalue123", "source": "env", "secret": True},
                    },
                }),
            )

        inspector = EnvInspector(eng, runner=fake_runner)
        inspector._find_package_cli = lambda _name: "/usr/local/bin/cfg-demo"
        rep_masked = inspector.inspect("cfg-demo", reveal=False)
        self.assertEqual(rep_masked["entries"]["SERVER_NAME"]["resolved"], "node-alpha")
        self.assertEqual(rep_masked["entries"]["SERVER_NAME"]["source"], "auto")
        self.assertIn("****", rep_masked["entries"]["API_SECRET"]["resolved"])
        self.assertEqual(rep_masked["entries"]["OPT_KEY"]["source"], "skip")

        rep_plain = inspector.inspect("cfg-demo", reveal=True)
        self.assertEqual(rep_plain["entries"]["API_SECRET"]["resolved"], "supersecretvalue123")

        self_rep = inspector.inspect("deploy-engine", reveal=False)
        self.assertEqual(self_rep["package"], "deploy-engine")
        self.assertIn("SYS_BIN", self_rep["entries"])

    def test_tree_state_keeper_preserves_expanded_and_cursor(self):
        class FakeNode:
            def __init__(self, key, expanded=False, children=None):
                self.data, self.is_expanded, self.children = {"key": key}, expanded, list(children or [])

            def expand(self):
                self.is_expanded = True

        child_pkg = FakeNode("core/setup-base", expanded=True)
        folder = FakeNode("folder:core", expanded=True, children=[child_pkg])
        root = FakeNode("__root__", expanded=True, children=[folder])

        class FakeTree:
            def __init__(self, r, cursor=None, sy=0):
                self.root, self.cursor_node = r, cursor
                self.scroll_offset = SimpleNamespace(y=sy)
                self.selected = self.scrolled_y = None

            def select_node(self, n):
                self.selected = n

            def scroll_to(self, y=0, animate=False):
                self.scrolled_y = y

        snap = TreeStateKeeper.capture(FakeTree(root, cursor=child_pkg, sy=14))
        new_child = FakeNode("core/setup-base", expanded=False)
        new_folder = FakeNode("folder:core", expanded=False, children=[new_child])
        tree_after = FakeTree(FakeNode("__root__", expanded=True, children=[new_folder]))
        TreeStateKeeper.restore(tree_after, snap)

        self.assertTrue(new_folder.is_expanded)
        self.assertTrue(new_child.is_expanded)
        self.assertIs(tree_after.selected, new_child)
        self.assertEqual(tree_after.scrolled_y, 14)

    def test_e2e_de_lib_and_setup_notifier_integration(self):
        workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        pkgs_root = os.path.join(workspace_root, "deploy-packages")
        if not os.path.isdir(pkgs_root):
            self.skipTest("deploy-packages directory not found")

        eng = self._make_sandbox_engine()
        eng.discover_packages([pkgs_root], force_rescan=True)
        self.assertTrue(eng.registry.has("de-lib"))
        self.assertTrue(eng.registry.has("setup-notifier"))

        _, web_dest, _, web_type = eng.get_paths_and_modes("setup-notifier:web")
        self.assertEqual(web_type, "web")
        self.assertTrue(web_dest.endswith(os.path.join("de_setup-notifier", "web")))

        eng.install_packages(["de-lib"])
        installed_lib_root = os.path.join(eng.provider.get_paths()["opt_dir"], "de_lib")
        self.assertTrue(os.path.isdir(os.path.join(installed_lib_root, "de_common")))
        res = subprocess.run(
            [sys.executable, "-c", "import de_common; print(de_common.__version__)"],
            env={**os.environ, "PYTHONPATH": installed_lib_root},
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(res.stdout.strip(), "1.0.0")


if __name__ == "__main__":
    unittest.main()
