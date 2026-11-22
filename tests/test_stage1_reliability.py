"""
Unit tests for Stage 1 improvements:
- PermissionError soft warning in config loading
- Missing package soft warnings with similar-name suggestions
- #AUTO# marker parsing, rendering, and resolution
- Cross-platform default system paths (Linux / macOS root / macOS user)
- Centralized macOS quarantine attribute cleanup in FileInstaller
"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files"))

from lib import config as de_config
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.env.env_parser import EnvParser
from lib.installer.file_installer import FileInstaller
from lib.installer.transaction_manager import TransactionManager
from lib.providers.macos_provider import MacOSProvider
from lib.providers.sandbox_provider import SandboxProvider
from lib.state.package_inspector import PackageInspector


class TestStage1Reliability(unittest.TestCase):
    """Тесты Этапа 1: надежность, #AUTO#, пути Linux/macOS, предупреждения и macOS quarantine."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_stage1_test_")
        de_config._WARNED_PERMISSION_PATHS.clear()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        de_config._WARNED_PERMISSION_PATHS.clear()

    def _create_sample_repo(self) -> str:
        repo = os.path.join(self.test_dir, "repo")
        pkg_dir = os.path.join(repo, "setup-zsh")
        os.makedirs(os.path.join(pkg_dir, "files"), exist_ok=True)
        with open(os.path.join(pkg_dir, "files", "run.sh"), "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho ok\n")
        manifest = {
            "name": "setup-zsh",
            "version": "1.0.0",
            "desc": "Настройка Zsh",
            "units": {"run.sh": {"src": "files/run.sh", "dest": "{{SYS_BIN}}/run.sh", "type": "script"}},
        }
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        return repo

    def test_permission_error_soft_warning_once(self):
        """PermissionError при чтении системного .env выдает мягкое предупреждение один раз и не роняет загрузку."""
        stderr_buf = io.StringIO()
        fake_path = Path("/etc/default/de_deploy-engine/deploy-engine.env")
        with mock.patch("sys.stderr", stderr_buf), mock.patch("sys.argv", ["deploy-engine", "list"]):
            with mock.patch.object(Path, "is_file", side_effect=PermissionError(13, "Permission denied")):
                res1 = de_config._safe_is_file(fake_path)
                res2 = de_config._safe_is_file(fake_path)
        self.assertIsNone(res1)
        self.assertIsNone(res2)
        err_text = stderr_buf.getvalue()
        self.assertIn("Предупреждение: нет прав на чтение", err_text)
        self.assertEqual(err_text.count("Предупреждение: нет прав на чтение"), 1)

    def test_parse_env_file_handles_permission_error_and_auto(self):
        """parse_env_file отсекает #AUTO# и безопасно обрабатывает PermissionError."""
        env_path = os.path.join(self.test_dir, "test.env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write('DE_SYS_BIN="#AUTO#"\nDE_ENV_PREFIX="de_"\nEMPTY=""\n')
        parsed = de_config.parse_env_file(env_path)
        self.assertNotIn("DE_SYS_BIN", parsed)
        self.assertNotIn("EMPTY", parsed)
        self.assertEqual(parsed.get("DE_ENV_PREFIX"), "de_")

        stderr_buf = io.StringIO()
        with mock.patch("sys.stderr", stderr_buf), mock.patch("sys.argv", ["deploy-engine", "list"]):
            with mock.patch("builtins.open", side_effect=PermissionError(13, "Permission denied")):
                res = de_config.parse_env_file(env_path)
        self.assertEqual(res, {})
        self.assertIn("Предупреждение", stderr_buf.getvalue())

    def test_env_parser_auto_marker_roundtrip(self):
        """EnvParser помечает #AUTO# флагом is_auto=True и сохраняет его в кавычках при рендере."""
        self.assertTrue(EnvParser.is_auto_value("#AUTO#"))
        self.assertTrue(EnvParser.is_auto_value("  #AUTO# "))
        self.assertFalse(EnvParser.is_auto_value("/usr/local/bin"))

        env_path = os.path.join(self.test_dir, "deploy.env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write('# Комментарий\nDE_SYS_BIN="#AUTO#"\nDE_ENV_PREFIX="de_"\n')
        parser = EnvParser()
        entries = parser.parse_editable_entries(env_path)
        by_key = {e["key"]: e for e in entries}
        self.assertTrue(by_key["DE_SYS_BIN"]["is_auto"])
        self.assertEqual(by_key["DE_SYS_BIN"]["value"], EnvParser.AUTO_MARKER)
        self.assertFalse(by_key["DE_ENV_PREFIX"]["is_auto"])

        rendered = parser.render_with_values(env_path, {"DE_SYS_BIN": "#AUTO#", "DE_ENV_PREFIX": "custom_"})
        self.assertIn('DE_SYS_BIN="#AUTO#"', rendered)
        self.assertIn('DE_ENV_PREFIX="custom_"', rendered)

    def test_cross_platform_default_paths_and_overrides(self):
        """Кроссплатформенные пути для Linux, macOS root и macOS user + ручное переопределение вместо #AUTO#."""
        linux_paths = de_config.get_platform_default_paths(platform_name="linux", is_root=True)
        self.assertEqual(linux_paths["DE_SYS_SYSTEMD"], "/etc/systemd/system")
        self.assertEqual(linux_paths["DE_ENV_PATH"], "/etc/default")
        self.assertEqual(linux_paths["DE_OPT_DIR"], "/opt")

        mac_root = de_config.get_platform_default_paths(platform_name="darwin", is_root=True, home_dir="/Users/tester")
        self.assertEqual(mac_root["DE_SYS_SYSTEMD"], "/Library/LaunchDaemons")
        self.assertEqual(mac_root["DE_ENV_PATH"], "/etc/default")
        self.assertEqual(mac_root["DE_OPT_DIR"], "/opt")

        mac_user = de_config.get_platform_default_paths(platform_name="darwin", is_root=False, home_dir="/Users/tester")
        self.assertEqual(mac_user["DE_SYS_SYSTEMD"], "/Users/tester/Library/LaunchAgents")
        self.assertEqual(mac_user["DE_ENV_PATH"], "/Users/tester/.config/deploy-engine/default")
        self.assertEqual(mac_user["DE_STATE_DIR"], "/Users/tester/.local/state/deploy-engine")
        self.assertEqual(mac_user["DE_OPT_DIR"], "/Users/tester/.local/opt")

        # load_config должен разрешать #AUTO# в платформенные пути, а явное значение сохранять
        cfg_auto = de_config.load_config(
            engine_root=self.test_dir,
            prod_config_path=Path(self.test_dir) / "missing.env",
            prod_data_dir=os.path.join(self.test_dir, "missing_data"),
            env_map={"DE_SYS_SYSTEMD": "#AUTO#", "DE_OPT_DIR": "/custom/opt"},
            platform_name="darwin",
            is_root=False,
            home_dir="/Users/tester",
        )
        self.assertEqual(cfg_auto["SYS_SYSTEMD"], "/Users/tester/Library/LaunchAgents")
        self.assertEqual(cfg_auto["OPT_DIR"], "/custom/opt")

        # MacOSProvider.get_paths уважает явный DE_SYS_BIN и игнорирует #AUTO#
        with mock.patch.dict(os.environ, {"DE_SYS_BIN": "/custom/mac/bin", "DE_ENV_PATH": "#AUTO#"}, clear=False):
            mp_paths = MacOSProvider(ExecutionContext(non_interactive=True)).get_paths()
        self.assertEqual(mp_paths["sys_bin"], "/custom/mac/bin")
        self.assertNotEqual(mp_paths["env_path"], "#AUTO#")

    def test_missing_package_warnings_and_suggestions(self):
        """Несуществующие пакеты в install / reinstall / uninstall / info выдают мягкое предупреждение и подсказку."""
        repo = self._create_sample_repo()
        logs = []
        ctx = ExecutionContext(non_interactive=True, sandbox=True)
        ctx.add_log_listener(logs.append)
        provider = SandboxProvider(ctx, sandbox_dir=os.path.join(self.test_dir, "sb"), target_os="debian")
        engine = Engine(ctx, provider=provider)
        engine.discover_packages(search_roots=[repo], force_rescan=True)

        self.assertFalse(engine.install_packages(["setup-zhs"]))
        self.assertFalse(engine.reinstall_package("setup-zhs"))
        self.assertFalse(engine.uninstall_package("setup-zhs"))

        joined = "\n".join(logs)
        self.assertIn("Предупреждение: пакет 'setup-zhs' не найден", joined)
        self.assertIn("setup-zsh", joined)

        inspector = PackageInspector(engine=engine)
        info_text = inspector.format_package_info("setup-zhs")
        self.assertIn("Предупреждение: пакет 'setup-zhs' не найден", info_text)
        self.assertIn("setup-zsh", info_text)

    def test_centralized_macos_quarantine_cleanup(self):
        """FileInstaller централизованно снимает com.apple.quarantine на macOS для скриптов и каталогов."""
        logs = []
        ctx = ExecutionContext(non_interactive=True, sandbox=False)
        ctx.add_log_listener(logs.append)
        provider = SandboxProvider(ctx, sandbox_dir=os.path.join(self.test_dir, "sb_mac"), target_os="macos")
        installer = FileInstaller(ctx, TransactionManager(), provider=provider)

        src_script = os.path.join(self.test_dir, "tool.sh")
        dest_script = os.path.join(self.test_dir, "out", "tool.sh")
        with open(src_script, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho hi\n")

        with mock.patch("sys.platform", "darwin"), mock.patch("shutil.which", return_value="/usr/bin/xattr"), mock.patch("subprocess.run") as run_mock:
            installer.install_file(src_script, dest_script, 0o755, "script")
            calls = [c.args[0] for c in run_mock.call_args_list]
            self.assertIn(["xattr", "-d", "com.apple.quarantine", dest_script], calls)

            run_mock.reset_mock()
            target_dir = os.path.join(self.test_dir, "pkg_dir")
            os.makedirs(target_dir, exist_ok=True)
            installer.clear_macos_quarantine(target_dir, recursive=True)
            dir_calls = [c.args[0] for c in run_mock.call_args_list]
            self.assertIn(["xattr", "-rd", "com.apple.quarantine", target_dir], dir_calls)


if __name__ == "__main__":
    unittest.main()
