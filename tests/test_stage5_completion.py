"""
Unit tests for Stage 5:
- `deploy-engine completion [commands|packages|installed]`
- Colon escaping for Zsh `_describe` format (`name:description`)
- Suppressed PermissionError stderr warnings during `completion`
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

import main as de_main
from lib import config as de_config
from lib.core.completion_provider import CompletionProvider
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.providers.sandbox_provider import SandboxProvider


class TestStage5Completion(unittest.TestCase):
    """Тесты Этапа 5: генерация подсказок автодополнения deploy-engine completion."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_stage5_test_")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        self.sb_dir = os.path.join(self.test_dir, "sandbox")
        os.makedirs(self.repo_dir, exist_ok=True)
        de_config._WARNED_PERMISSION_PATHS.clear()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        de_config._WARNED_PERMISSION_PATHS.clear()

    def _create_pkg(self, name: str, desc: str, platforms=None) -> None:
        pkg_dir = os.path.join(self.repo_dir, name)
        os.makedirs(os.path.join(pkg_dir, "files"), exist_ok=True)
        with open(os.path.join(pkg_dir, "files", "run.sh"), "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho ok\n")
        manifest = {
            "name": name,
            "version": "1.2.0",
            "desc": desc,
            "units": {"run.sh": {"src": "files/run.sh", "dest": "{{SYS_BIN}}/run.sh", "type": "script"}},
        }
        if platforms:
            manifest["platforms"] = platforms
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

    def test_completion_provider_commands_packages_and_installed(self):
        """CompletionProvider корректно выводит команды, совместимые пакеты (с экранированием ':') и установленные."""
        self._create_pkg("setup-zsh", "Настройка Zsh: плагины и промпт", platforms=["debian"])
        self._create_pkg("mac-only", "Только для macOS", platforms=["macos"])

        ctx = ExecutionContext(non_interactive=True, sandbox=True)
        provider = SandboxProvider(ctx, sandbox_dir=self.sb_dir, target_os="debian")
        engine = Engine(ctx, provider=provider)
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)

        cp = CompletionProvider(engine)

        # 1. Команды
        cmds_out = cp.render("commands")
        self.assertIn("install:", cmds_out)
        self.assertIn("config:", cmds_out)

        # 2. Доступные пакеты (только совместимые с debian + экранирование двоеточия в описании)
        pkgs_out = cp.render("packages")
        self.assertIn("setup-zsh:Настройка Zsh\\: плагины и промпт", pkgs_out)
        self.assertNotIn("mac-only:", pkgs_out)

        # 3. Установленные пакеты
        self.assertEqual(cp.render("installed"), "")
        engine.install_packages(["setup-zsh"])
        inst_out = cp.render("installed")
        self.assertIn("setup-zsh:", inst_out)
        self.assertIn("v1.2.0", inst_out)

    def test_main_completion_routing_and_silent_permission_warning(self):
        """main.py распознает 'completion' и config.py подавляет предупреждения PermissionError в stderr."""
        parser = de_main.build_parser()
        args = parser.parse_args(["completion", "packages"])
        action, targets = de_main.resolve_mode_and_targets(args)
        self.assertEqual(action, "completion")
        self.assertEqual(targets, ["packages"])

        stderr_buf = io.StringIO()
        with mock.patch("sys.stderr", stderr_buf), mock.patch("sys.argv", ["deploy-engine", "completion", "packages"]):
            with mock.patch.object(Path, "is_file", side_effect=PermissionError(13, "denied")):
                de_config._safe_is_file(Path("/etc/default/de_deploy-engine/deploy-engine.env"))
        self.assertEqual(stderr_buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
