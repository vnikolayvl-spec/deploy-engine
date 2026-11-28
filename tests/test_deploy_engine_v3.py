"""
Тесты ядра и .env-подсистемы Deploy Engine v3.0.0:
- версия 3.0.0, SemVer-сравнение и ограничения, min_engine_version, EDITOR_FALLBACKS;
- порядок установки (CLI + мягкий after + SemVer requires);
- сохранение комментариев/инлайн-комментариев в .env, #GEN:...#, #GEN:pkg:...#, безопасный #SKIP#.
"""
import os
import shutil
import sys
import tempfile
import unittest

DE_FILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files")
if DE_FILES_DIR not in sys.path:
    sys.path.insert(0, DE_FILES_DIR)

from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.core.version_utils import (
    check_min_engine_version,
    compare_semver,
    get_engine_version,
    parse_requirement,
    satisfies_constraints,
    version_status,
)
from lib.dependencies.dependency_graph import DependencyGraph
from lib.discovery.package_registry import PackageRegistry
from lib.env.env_config_editor import EnvConfigEditor
from lib.env.env_parser import EnvParser
from lib.env.env_upsert_manager import EnvUpsertManager
from lib.installer.transaction_manager import TransactionManager


class TestDeployEngineV3Core(unittest.TestCase):
    """Тесты ядра v3.0.0: SemVer, порядок установки, комментарии .env, #GEN# и #SKIP#."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="de_v3_core_")
        self.env_dir = os.path.join(self.tmp, "local_env")
        os.makedirs(self.env_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_version_and_editor_fallbacks(self):
        self.assertEqual(get_engine_version(), "3.1.0")
        self.assertEqual(EnvConfigEditor.EDITOR_FALLBACKS, ("vim", "vi", "nano"))
        self.assertEqual(compare_semver("1.2.0", "1.10.0"), -1)
        self.assertEqual(compare_semver("2.0.0-rc1", "2.0.0"), -1)
        self.assertEqual(version_status("1.0.0", "1.1.0"), "upgrade")
        self.assertEqual(version_status("1.1.0", "1.1.0"), "current")
        self.assertEqual(version_status("2.0.0", "1.5.0"), "downgrade")

        name, constraints = parse_requirement("de-lib>=1.0.0,<2.0.0")
        self.assertEqual(name, "de-lib")
        self.assertTrue(satisfies_constraints("1.5.0", constraints))
        self.assertFalse(satisfies_constraints("2.0.0", constraints))
        self.assertFalse(satisfies_constraints("0.9.9", constraints))

        ok, _ = check_min_engine_version({"name": "demo", "min_engine_version": "3.0.0"}, "3.0.0")
        self.assertTrue(ok)
        ok_bad, msg = check_min_engine_version({"name": "demo", "min_engine_version": "4.0.0"}, "3.0.0")
        self.assertFalse(ok_bad)
        self.assertIn("4.0.0", msg)

    def test_cli_order_soft_after_and_semver_requires(self):
        reg = PackageRegistry()
        reg.register({"name": "setup-base", "version": "1.2.0", "requires": [], "after": [], "units": {}})
        reg.register({"name": "setup-zsh", "version": "1.0.0", "requires": [], "after": ["setup-base"], "units": {}})
        reg.register({"name": "setup-limits", "version": "1.0.0", "requires": [], "after": [], "units": {}})
        reg.register({"name": "app-web", "version": "1.0.0", "requires": ["setup-base>=1.0.0"], "after": [], "units": {}})
        reg.register({"name": "app-too-new", "version": "1.0.0", "requires": ["setup-base>=2.0.0"], "after": [], "units": {}})

        graph = DependencyGraph(reg)
        self.assertEqual(graph.resolve_order(["setup-limits", "setup-base"]), ["setup-limits", "setup-base"])
        self.assertEqual(graph.resolve_order(["setup-zsh", "setup-base"]), ["setup-base", "setup-zsh"])
        self.assertEqual(graph.resolve_order(["setup-zsh"]), ["setup-zsh"])
        self.assertEqual(graph.resolve_order(["app-web"]), ["setup-base", "app-web"])
        with self.assertRaises(DeployEngineError):
            graph.resolve_order(["app-too-new"])

    def test_env_comments_gen_and_safe_skip(self):
        tmpl = os.path.join(self.tmp, "deploy.env")
        dest = os.path.join(self.tmp, "sys", "demo.env")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(tmpl, "w", encoding="utf-8") as f:
            f.write(
                "# Базовая конфигурация\n"
                'APP_HOST="localhost"  # Хост приложения\n'
                'API_TOKEN="#GEN:hex:24#"\n'
                'SHORT_PASS="#GEN:pass:16#"\n'
                'REQ_ID="#GEN:uuid#"\n'
                'FREE_PORT="#GEN:port:41000-42000#"\n'
                'WG_PRIV="#GEN:pkg:wireguard_key#"\n'
                'OPT_SECRET="{{PROMPT:Секрет опционально}}"\n'
            )

        ctx = ExecutionContext(non_interactive=True)
        mgr = EnvUpsertManager(ctx, TransactionManager(), local_env_dir=self.env_dir)

        preset = mgr.save_local_preset("demo", tmpl, {"APP_HOST": "prod.local", "OPT_SECRET": "#SKIP#"})
        with open(preset, encoding="utf-8") as fh:
            preset_text = fh.read()
        self.assertIn("# Базовая конфигурация", preset_text)
        self.assertIn("# Хост приложения", preset_text)
        self.assertIn('OPT_SECRET="#SKIP#"', preset_text)
        self.assertIn('WG_PRIV="#GEN:pkg:wireguard_key#"', preset_text)
        self.assertNotIn("#GEN:hex:24#", preset_text)
        self.assertFalse(mgr.needs_env_confirmation("demo", tmpl))

        mgr.upsert_env_file(tmpl, dest, pkg_name="demo")
        with open(dest, encoding="utf-8") as fh:
            sys_text = fh.read()
        self.assertIn('OPT_SECRET=""  # #SKIP#', sys_text)
        self.assertNotIn('OPT_SECRET="#SKIP#"', sys_text)
        sys_kv, _ = EnvParser().parse_file(dest)
        self.assertEqual(len(sys_kv["API_TOKEN"]), 24)
        self.assertEqual(len(sys_kv["SHORT_PASS"]), 16)
        self.assertEqual(len(sys_kv["REQ_ID"]), 36)
        self.assertTrue(41000 <= int(sys_kv["FREE_PORT"]) <= 42000)
        self.assertEqual(sys_kv["WG_PRIV"], "#GEN:pkg:wireguard_key#")

        with open(preset, "a", encoding="utf-8") as f:
            f.write("\n# Новая опция логирования\nLOG_LEVEL=debug\n")
        mgr.upsert_env_file(tmpl, dest, pkg_name="demo")
        with open(dest, encoding="utf-8") as fh:
            updated_sys = fh.read()
        self.assertIn("# Новая опция логирования", updated_sys)
        self.assertIn("LOG_LEVEL=debug", updated_sys)


if __name__ == "__main__":
    unittest.main()
