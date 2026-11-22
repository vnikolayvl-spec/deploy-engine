"""
Unit tests for Stage 2 & Stage 3:
- Stage 2: Internal preset storage without modifying repo files, applying preset to system .env
  for installed packages (with PermissionError fallback), and `deploy-engine config <pkg> [--preset]`.
- Stage 3: Mandatory pre-install .env confirmation ONLY for packages without a saved preset,
  strictly BEFORE sys_packages installation and file deployment in both CLI and TUI ExecutionModal.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from types import ModuleType, SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files"))

import main as de_main
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.env.env_config_editor import EnvConfigEditor
from lib.env.env_confirmation_gate import EnvConfirmationGate
from lib.providers.sandbox_provider import SandboxProvider


class TestStage2AndStage3Env(unittest.TestCase):
    """Тесты Этапов 2 и 3: хранилище пресетов, deploy-engine config и обязательное подтверждение .env."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_stage23_test_")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        self.sb_dir = os.path.join(self.test_dir, "sandbox")
        self.preset_dir = os.path.join(self.test_dir, "presets")
        os.makedirs(self.repo_dir, exist_ok=True)
        os.makedirs(self.preset_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_pkg(self, name: str, env_text: str, sys_pkgs=None) -> str:
        pkg_dir = os.path.join(self.repo_dir, name)
        os.makedirs(os.path.join(pkg_dir, "files"), exist_ok=True)
        env_path = os.path.join(pkg_dir, "deploy.env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_text)
        with open(os.path.join(pkg_dir, "files", "run.sh"), "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho ok\n")
        manifest = {
            "name": name,
            "version": "1.0.0",
            "desc": f"Пакет {name}",
            "sys_packages": sys_pkgs or [],
            "units": {
                "deploy.env": {"type": "env"},
                "run.sh": {"src": "files/run.sh", "dest": "{{SYS_BIN}}/run.sh", "type": "script"},
            },
        }
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        return env_path

    def _build_engine(self, non_interactive: bool = True):
        logs = []
        ctx = ExecutionContext(non_interactive=non_interactive, sandbox=True)
        ctx.add_log_listener(logs.append)
        provider = SandboxProvider(ctx, sandbox_dir=self.sb_dir, target_os="debian")
        engine = Engine(ctx, provider=provider)
        engine.env_manager.local_env_dir = self.preset_dir
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)
        return engine, logs

    def test_stage2_preset_storage_and_apply_to_system_env_leaves_repo_untouched(self):
        """Пресет сохраняется во внутреннее хранилище, репозиторий не тронут, а apply обновляет системный .env с бэкапом."""
        orig_env = 'APP_PORT="8080"\nAPP_MODE="#AUTO#"\n'
        repo_env = self._create_pkg("demo-app", orig_env)
        engine, _ = self._build_engine(non_interactive=True)
        engine.install_packages(["demo-app"])

        _, dest_path, _, _ = engine.get_paths_and_modes("demo-app:deploy.env")
        self.assertTrue(os.path.isfile(dest_path))

        preset_path, warn = engine.env_manager.apply_preset_to_system_env(
            "demo-app", repo_env, dest_path, {"APP_PORT": "9090", "APP_MODE": "#AUTO#"}
        )
        self.assertIsNone(warn)
        self.assertTrue(os.path.isfile(preset_path))
        self.assertTrue(os.path.isfile(f"{dest_path}.de_bak"))

        # Репозиторий не изменился ни на байт!
        with open(repo_env, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), orig_env)
        # Системный .env и пресет обновлены
        with open(dest_path, "r", encoding="utf-8") as f:
            sys_text = f.read()
        self.assertIn('APP_PORT="9090"', sys_text)
        self.assertIn('APP_MODE="#AUTO#"', sys_text)

        # Мягкое предупреждение при PermissionError на системный .env
        with mock.patch("builtins.open", side_effect=[mock.mock_open(read_data=orig_env)(), PermissionError(13, "denied")]):
            with mock.patch.object(engine.env_manager, "save_local_preset", return_value=preset_path):
                _, p_warn = engine.env_manager.apply_preset_to_system_env("demo-app", repo_env, dest_path, {"APP_PORT": "7070"})
        self.assertIsNotNone(p_warn)
        self.assertIn("нет прав на запись", p_warn)

    def test_stage2_deploy_engine_config_command_system_and_preset(self):
        """deploy-engine config <pkg> открывает системный .env, а --preset открывает и инициализирует пресет."""
        orig_env = 'API_KEY="{{PROMPT:Ключ:default_val}}"\n'
        repo_env = self._create_pkg("web-svc", orig_env)
        engine, logs = self._build_engine(non_interactive=True)

        # Проверка разбора CLI-аргументов main.py
        parser = de_main.build_parser()
        args = parser.parse_args(["config", "web-svc", "--preset"])
        action, targets = de_main.resolve_mode_and_targets(args)
        self.assertEqual(action, "config")
        self.assertEqual(targets, ["web-svc"])
        self.assertTrue(args.preset)

        launched = []
        editor = EnvConfigEditor(engine, runner=lambda cmd: (launched.append(cmd), SimpleNamespace(returncode=0))[1])

        with mock.patch.dict(os.environ, {"EDITOR": "nano -w"}, clear=False):
            # 1. До установки: без --preset выдает мягкое предупреждение и советует --preset
            self.assertFalse(editor.open_config("web-svc", preset=False))
            self.assertIn("--preset", "\n".join(logs))

            # 2. С --preset: создает пресет из шаблона (репозиторий не тронут!) и открывает его
            self.assertTrue(editor.open_config("web-svc", preset=True))
            self.assertEqual(launched[-1][0:2], ["nano", "-w"])
            self.assertEqual(launched[-1][2], engine.env_manager.get_local_preset_path("web-svc"))
            with open(repo_env, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), orig_env)

            # 3. После установки: без --preset открывает системный .env
            engine.install_packages(["web-svc"])
            _, dest_path, _, _ = engine.get_paths_and_modes("web-svc:deploy.env")
            self.assertTrue(editor.open_config("web-svc", preset=False))
            self.assertEqual(launched[-1][2], dest_path)

            # 4. Несуществующий пакет: мягкое предупреждение с подсказкой
            logs.clear()
            self.assertFalse(editor.open_config("web-scv", preset=False))
            self.assertIn("web-svc", "\n".join(logs))

    def test_stage3_cli_mandatory_env_confirmation_before_sys_packages(self):
        """В CLI подтверждение .env выполняется ДО sys_manager.install_packages и только без сохраненного пресета."""
        self._create_pkg("sec-app", 'SECRET="{{PROMPT:Секрет}}"\nMODE="prod"\n', sys_pkgs=["curl"])
        engine, logs = self._build_engine(non_interactive=False)

        # 1. Пользователь отменяет на этапе подтверждения (n) -> sys_manager.install_packages НЕ вызывается!
        answers_cancel = iter(["my_secret_123", "n"])
        with mock.patch.object(engine.sys_manager, "install_packages") as sys_mock:
            with mock.patch.object(EnvConfirmationGate, "_default_input", side_effect=lambda _p: next(answers_cancel)):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    ok = engine.install_packages(["sec-app"])
        self.assertFalse(ok)
        sys_mock.assert_not_called()
        self.assertIsNone(engine.state_repo.get_installed_package("sec-app"))

        # 2. Пользователь подтверждает (Y) -> сохраняется пресет, затем вызываются sys_packages и установка
        answers_ok = iter(["my_secret_123", "y"])
        call_order = []
        orig_save = engine.env_manager.save_local_preset

        def _spy_save(*a, **kw):
            call_order.append("save_preset")
            return orig_save(*a, **kw)

        with mock.patch.object(engine.env_manager, "save_local_preset", side_effect=_spy_save):
            with mock.patch.object(engine.sys_manager, "install_packages", side_effect=lambda _p: call_order.append("sys_install")):
                with mock.patch.object(EnvConfirmationGate, "_default_input", side_effect=lambda _p: next(answers_ok)):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        ok = engine.install_packages(["sec-app"])
        self.assertTrue(ok)
        self.assertEqual(call_order, ["save_preset", "sys_install"])
        self.assertTrue(engine.env_manager.has_saved_preset("sec-app"))

        # 3. Повторная проверка: пресет уже сохранен -> подтверждение НЕ требуется!
        self.assertFalse(engine.env_manager.needs_env_confirmation("sec-app", os.path.join(self.repo_dir, "sec-app", "deploy.env")))
        self.assertEqual(EnvConfirmationGate.collect_unconfirmed_packages(engine, ["sec-app"]), [])

    def test_stage3_tui_execution_modal_barrier_blocks_and_cancels_before_plan(self):
        """В TUI барьер ExecutionModal запускается ДО execute_plan_synchronously и позволяет отменить установку."""
        try:
            import textual  # noqa: F401
        except ImportError:
            class _Meta(type):
                def __getattr__(cls, _name): return object

            class _Dummy(metaclass=_Meta):
                def __init__(self, *a, **kw): pass

            for mod_name, attrs in {
                "textual": {}, "textual.app": {"App": _Dummy, "ComposeResult": object},
                "textual.containers": {"Horizontal": _Dummy, "Vertical": _Dummy, "VerticalScroll": _Dummy},
                "textual.screen": {"ModalScreen": _Dummy},
                "textual.widgets": {"Button": _Dummy, "Input": _Dummy, "Label": _Dummy, "RichLog": _Dummy},
            }.items():
                m = ModuleType(mod_name)
                for k, v in attrs.items(): setattr(m, k, v)
                sys.modules[mod_name] = m

        from lib.ui.execution_modal import ExecutionModal

        self._create_pkg("tui-app", 'TOKEN="default_tok"\n')
        engine, _ = self._build_engine(non_interactive=True)

        modal = ExecutionModal(engine, {"tui-app": "install"})
        evt = threading.Event()
        fake_panel = SimpleNamespace(approved=False, cancelled=True, approval_event=evt, approved_values={"TOKEN": "x"})
        evt.set()
        modal.env_panels["tui-app"] = fake_panel
        type(modal).app = property(lambda _s: SimpleNamespace(call_from_thread=lambda fn, *a: fn(*a)))
        modal._trigger_pkg_env_tab = lambda _p: None
        modal._finalize_pkg_env_after_approval = lambda _p: None
        modal._switch_active_tab = lambda _t: None
        modal._on_execution_finished = lambda ok, msg=None: setattr(modal, "_fin", (ok, msg))
        modal._write_line = lambda *_a: None

        with mock.patch.object(modal, "execute_plan_synchronously") as exec_mock:
            modal._run_operations_thread()
        exec_mock.assert_not_called()
        self.assertFalse(modal._fin[0])
        self.assertIn("отменена", modal._fin[1])

    def test_stage3_non_interactive_blocks_missing_required_env(self):
        """В режиме --yes незаполненный обязательный {{PROMPT:...}} без дефолта блокирует установку до sys_packages."""
        tpl_path = self._create_pkg("strict-app", 'API_TOKEN="{{PROMPT:Токен доступа}}"\nPORT="{{PROMPT:Порт:8080}}"\n', sys_pkgs=["jq"])
        engine, _ = self._build_engine(non_interactive=True)

        # 1. Без пресета и системного .env -> DeployEngineError до запуска sys_manager.install_packages
        with mock.patch.object(engine.sys_manager, "install_packages") as sys_mock:
            with self.assertRaises(DeployEngineError) as err_ctx:
                engine.install_packages(["strict-app"])
        sys_mock.assert_not_called()
        self.assertIn("API_TOKEN", str(err_ctx.exception))
        self.assertIn("deploy-engine config strict-app --preset", str(err_ctx.exception))
        self.assertIsNone(engine.state_repo.get_installed_package("strict-app"))

        # 2. С --dry-run не блокирует симуляцию
        engine.context.dry_run = True
        self.assertTrue(engine.install_packages(["strict-app"]))
        engine.context.dry_run = False

        # 3. После заполнения пресета установка с --yes проходит успешно
        engine.env_manager.save_local_preset("strict-app", tpl_path, {"API_TOKEN": "tok-123", "PORT": "8080"})
        self.assertTrue(engine.install_packages(["strict-app"]))
        self.assertIsNotNone(engine.state_repo.get_installed_package("strict-app"))

        # 4. Удаление пресета: без --clean-env системный .env сохраняет API_TOKEN (reinstall проходит), с --clean-env -> ошибка
        os.remove(engine.env_manager.get_local_preset_path("strict-app"))
        self.assertTrue(engine.reinstall_package("strict-app"))
        engine.context.clean_env = True
        with self.assertRaises(DeployEngineError):
            engine.install_packages(["strict-app"])


if __name__ == "__main__":
    unittest.main()
