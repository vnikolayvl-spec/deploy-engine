"""
Unit tests for two-tier RemoteDeployer (--remote and --remote-dir):
- Full Mode when deploy-engine is installed on the remote server (/opt/de_deploy-engine or custom --remote-dir)
- Reduced Mode when deploy-engine is absent on the remote server (allows install/uninstall/reinstall/list; blocks backup/restore/info/tui)
- Client-Server Remote TUI preparation and plan execution (Variant 2)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files"))

from lib.core.deploy_engine_error import DeployEngineError
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.remote.remote_deployer import RemoteDeployer


class TestRemoteModes(unittest.TestCase):
    """Проверка Полного и Сокращенного режимов --remote, ключа --remote-dir и Remote TUI."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_remote_test_")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        os.makedirs(self.repo_dir, exist_ok=True)

        pkg_dir = os.path.join(self.repo_dir, "net", "vpn-agent")
        os.makedirs(pkg_dir, exist_ok=True)
        with open(os.path.join(pkg_dir, "deploy.env"), "w", encoding="utf-8") as f:
            f.write("VPN_PORT=51820\n")
        with open(os.path.join(pkg_dir, "agent.sh"), "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho vpn\n")
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": "vpn-agent",
                    "version": "1.4.0",
                    "desc": "Удаленный VPN агент",
                    "units": {
                        "deploy.env": {"type": "env"},
                        "agent.sh": {"type": "script"},
                    },
                },
                f,
            )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_fake_ssh(self, engine_installed_at=None, remote_state=None, remote_os="Linux\nubuntu"):
        """Создает мок SSHClient без второго класса в файле."""
        executed_commands = []
        scp_transfers = []
        state_json = json.dumps(remote_state or {"installed": {"vpn-agent": {"version": "1.4.0", "files": []}}})

        def run_command(command: str, capture_output: bool = False):
            executed_commands.append(command)
            stdout = ""
            if "__MISSING__" in command and "if [ -f " in command:
                stdout = f"{engine_installed_at}\n" if engine_installed_at else "__MISSING__\n"
            elif "deploy.py list --json" in command or "cat /etc/default/state.json" in command:
                stdout = state_json
            elif "uname -s" in command:
                stdout = remote_os
            return subprocess.CompletedProcess(args=["ssh"], returncode=0, stdout=stdout, stderr="")

        def scp_file(local_path: str, remote_path: str):
            scp_transfers.append((local_path, remote_path))

        fake = type("FakeSSH", (), {"target_host": "admin@10.0.0.5", "run_command": staticmethod(run_command), "scp_file": staticmethod(scp_file)})()
        return fake, executed_commands, scp_transfers

    def test_reduced_mode_allows_basic_and_blocks_backup_restore_info_tui(self):
        """
        В сокращенном режиме (когда на сервере нет /opt/de_deploy-engine):
        - list, install, uninstall, reinstall работают;
        - backup, restore, info и TUI блокируются с понятным сообщением.
        """
        fake_ssh, cmds, scps = self._make_fake_ssh(engine_installed_at=None)
        ctx = ExecutionContext(remote="admin@10.0.0.5", json_output=True)
        engine = Engine(ctx)
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)

        deployer = RemoteDeployer("admin@10.0.0.5", ctx, ssh_client=fake_ssh)
        self.assertFalse(deployer.is_full_mode())

        # 1. Блокировка backup, restore, info, tui в сокращенном режиме
        for forbidden_action in ("backup", "restore", "info", "tui"):
            with self.assertRaises(DeployEngineError) as err_ctx:
                deployer.ensure_action_supported(forbidden_action)
            self.assertIn("сокращенном режиме", str(err_ctx.exception))
            self.assertIn("--remote-dir", str(err_ctx.exception))

        # 2. Разрешенные операции (install и list) в сокращенном режиме проходят через временный бандл
        deployer.execute_remote(["vpn-agent"], action="install", engine=engine)
        self.assertTrue(any("/tmp/de_deploy_run" in c for c in cmds))
        self.assertEqual(len(scps), 1)

    def test_full_mode_custom_remote_dir_and_backup_restore_info_tui(self):
        """
        В полном режиме (когда deploy-engine найден в /opt/de_deploy-engine или по кастомному --remote-dir):
        - работают backup (--comment, --list), restore (--backup), info, list и Remote TUI (Вариант 2).
        """
        custom_dir = "/srv/custom_de_engine/files"
        fake_ssh, cmds, scps = self._make_fake_ssh(
            engine_installed_at=custom_dir,
            remote_state={"installed": {"vpn-agent": {"version": "1.4.0", "files": ["/usr/local/bin/agent.sh"]}}},
            remote_os="Linux\ndebian",
        )
        ctx = ExecutionContext(
            remote="admin@10.0.0.5",
            remote_dir="/srv/custom_de_engine",
            comment="Бэкап перед апгрейдом",
            backup_selector="2",
        )
        engine = Engine(ctx)
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)

        deployer = RemoteDeployer("admin@10.0.0.5", ctx, remote_dir="/srv/custom_de_engine", ssh_client=fake_ssh)
        self.assertTrue(deployer.is_full_mode())
        self.assertEqual(deployer.probe_remote_engine(), custom_dir)

        # 1. Выполнение backup в полном режиме вызывает серверный main.py/deploy.py с --comment
        deployer.execute_remote(["vpn-agent"], action="backup", engine=engine)
        self.assertTrue(any("backup vpn-agent" in c and "--comment" in c for c in cmds))

        # 2. Выполнение restore в полном режиме передает селектор --backup 2
        deployer.execute_remote(["vpn-agent"], action="restore", engine=engine)
        self.assertTrue(any("restore vpn-agent" in c and "--backup 2" in c for c in cmds))

        # 3. Выполнение info в полном режиме синхронизирует метаданные и вызывает info
        deployer.execute_remote(["vpn-agent"], action="info", engine=engine)
        self.assertTrue(any("info vpn-agent" in c for c in cmds))

        # 4. Подготовка Клиент-Серверного Remote TUI (Вариант 2) загружает состояние сервера в локальный Engine
        resolved_dir = deployer.prepare_remote_tui(engine)
        self.assertEqual(resolved_dir, custom_dir)
        self.assertIsNotNone(engine.state_repo.get_installed_package("vpn-agent"))
        self.assertEqual(engine.provider.distro_id, "debian")

        # 5. Выполнение плана из Remote TUI отправляет команды на удаленный сервер
        deployer.execute_tui_plan({"vpn-agent": "reinstall"}, engine)
        self.assertTrue(any("reinstall vpn-agent" in c for c in cmds))

    def test_deploy_config_hierarchy_and_dual_mode_paths(self):
        """
        Проверка иерархической загрузки lib/config.py (os.environ -> custom -> prod -> app.env -> defaults)
        и переключения всех динамических путей (packages/, backup/, env/, packages.json) в /var/lib/de_deploy-engine.
        """
        from pathlib import Path
        from lib.config import load_config

        fake_root = os.path.join(self.test_dir, "local_engine")
        os.makedirs(fake_root, exist_ok=True)
        local_app_env = Path(fake_root) / "app.env"
        local_app_env.write_text(
            '# Комментарий\nDE_REMOTE_ENGINE_DIR="/custom/from_app_env"\nDE_BACKUP_DIR="{{PROMPT:Путь к бэкапам}}"\n',
            encoding="utf-8",
        )

        # 1. Автономный режим (Standalone)
        standalone_cfg = load_config(
            engine_root=fake_root,
            prod_config_path=Path(self.test_dir) / "nonexistent_prod.env",
            prod_data_dir=os.path.join(self.test_dir, "nonexistent_var_lib"),
            env_map={},
        )
        self.assertEqual(standalone_cfg["IS_PROD"], "false")
        self.assertEqual(standalone_cfg["ENGINE_DATA_DIR"], fake_root)
        self.assertEqual(standalone_cfg["PACKAGES_DIR"], "./packages")
        self.assertEqual(standalone_cfg["BACKUP_DIR"], os.path.join(fake_root, "backup"))
        self.assertEqual(standalone_cfg["LOCAL_ENV_DIR"], os.path.join(fake_root, "env"))
        self.assertEqual(standalone_cfg["DEFAULT_REMOTE_ENGINE_DIR"], "/custom/from_app_env")

        # 2. Системный продакшен-режим (/etc/default/de_deploy-engine/deploy-engine.env + /var/lib/de_deploy-engine)
        prod_env_file = Path(self.test_dir) / "deploy-engine.env"
        prod_env_file.write_text('DE_REMOTE_ENGINE_DIR="/opt/prod_remote_de"\n', encoding="utf-8")
        prod_var_lib = "/var/lib/de_deploy-engine"

        prod_cfg = load_config(
            engine_root="/opt/de_deploy-engine/files",
            prod_config_path=prod_env_file,
            prod_data_dir=prod_var_lib,
            env_map={},
        )
        self.assertEqual(prod_cfg["IS_PROD"], "true")
        self.assertEqual(prod_cfg["ENGINE_DATA_DIR"], "/var/lib/de_deploy-engine")
        self.assertEqual(prod_cfg["PACKAGES_DIR"], "/var/lib/de_deploy-engine/packages")
        self.assertEqual(prod_cfg["BACKUP_DIR"], "/var/lib/de_deploy-engine/backup")
        self.assertEqual(prod_cfg["LOCAL_ENV_DIR"], "/var/lib/de_deploy-engine/env")
        self.assertEqual(prod_cfg["PACKAGES_CACHE_FILE"], "/var/lib/de_deploy-engine/packages.json")
        self.assertEqual(prod_cfg["DEFAULT_REMOTE_ENGINE_DIR"], "/opt/prod_remote_de")

    def test_self_package_installation_in_sandbox(self):
        """
        Проверка самоустановки пакета deploy-engine по его собственному manifest.json (без post_install):
        - автоматические права 0755 на /opt/de_deploy-engine/files/main.py;
        - декларативное создание /var/lib/de_deploy-engine/{packages,backup,env};
        - отображение всех созданных системных путей (включая родительские папки и dirs) в info;
        - вывод подсказки ручного удаления оставшихся системных каталогов при uninstall.
        """
        import stat
        from lib.state.package_inspector import PackageInspector

        pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sb_dir = os.path.join(self.test_dir, "self_install_sb")
        ctx = ExecutionContext(non_interactive=True, sandbox=True, sandbox_os="debian", sandbox_dir=sb_dir)
        engine = Engine(context=ctx)
        engine.load_manifest_recursive(os.path.join(pkg_root, "manifest.json"))

        self.assertTrue(engine.registry.has("deploy-engine"))
        engine.install_packages(["deploy-engine"])

        main_py_dest = os.path.join(sb_dir, "opt/de_deploy-engine/files/main.py")
        self.assertTrue(os.path.isfile(main_py_dest))
        self.assertEqual(stat.S_IMODE(os.stat(main_py_dest).st_mode), 0o755)
        self.assertTrue(os.path.isfile(os.path.join(sb_dir, "opt/de_deploy-engine/files/lib/config.py")))
        self.assertTrue(os.path.isfile(os.path.join(sb_dir, "etc/default/de_deploy-engine/deploy-engine.env")))
        self.assertTrue(os.path.isfile(os.path.join(sb_dir, "usr/local/bin/deploy-engine.sh")))
        self.assertTrue(os.path.islink(os.path.join(sb_dir, "usr/local/bin/deploy-engine")))
        self.assertTrue(os.path.isfile(os.path.join(sb_dir, "usr/local/bin/deploy-ui.sh")))
        self.assertTrue(os.path.islink(os.path.join(sb_dir, "usr/local/bin/deploy-ui")))
        self.assertTrue(os.path.isdir(os.path.join(sb_dir, "var/lib/de_deploy-engine/packages")))
        self.assertTrue(os.path.isdir(os.path.join(sb_dir, "var/lib/de_deploy-engine/backup")))
        self.assertTrue(os.path.isdir(os.path.join(sb_dir, "var/lib/de_deploy-engine/env")))

        inspector = PackageInspector(state_repo=engine.state_repo, engine=engine)
        info = inspector.get_package_info("deploy-engine")
        info_paths = [f["path"] for f in info["files"]]
        self.assertIn(os.path.join(sb_dir, "opt/de_deploy-engine"), info_paths)
        self.assertIn(os.path.join(sb_dir, "etc/default/de_deploy-engine"), info_paths)
        self.assertIn(os.path.join(sb_dir, "var/lib/de_deploy-engine"), info_paths)
        self.assertIn(os.path.join(sb_dir, "var/lib/de_deploy-engine/packages"), info_paths)

        engine.uninstall_package("deploy-engine")
        self.assertFalse(os.path.exists(main_py_dest))
        self.assertTrue(os.path.isdir(os.path.join(sb_dir, "etc/default/de_deploy-engine")))
        self.assertTrue(os.path.isdir(os.path.join(sb_dir, "var/lib/de_deploy-engine")))

    def test_main_mode_resolution_and_keyboard_interrupt_rollback(self):
        """
        Проверка единой точки входа main.py (маршрутизация CLI vs TUI)
        и автоматического отката транзакции (LIFO) при нажатии Ctrl+C (KeyboardInterrupt).
        """
        from main import build_parser, resolve_mode_and_targets

        parser = build_parser()
        # 1. Маршрутизация: без CLI-команды -> TUI, с командой или --info -> CLI
        self.assertEqual(resolve_mode_and_targets(parser.parse_args([]))[0], "tui")
        self.assertEqual(resolve_mode_and_targets(parser.parse_args([self.repo_dir]))[0], "tui")
        self.assertEqual(resolve_mode_and_targets(parser.parse_args(["--sandbox", "macos"]))[0], "tui")
        self.assertEqual(resolve_mode_and_targets(parser.parse_args(["--tui"]))[0], "tui")
        self.assertEqual(resolve_mode_and_targets(parser.parse_args(["install", "vpn-agent"])), ("install", ["vpn-agent"]))
        self.assertEqual(resolve_mode_and_targets(parser.parse_args(["list"]))[0], "list")
        self.assertEqual(resolve_mode_and_targets(parser.parse_args(["--info", "vpn-agent"])), ("info", ["vpn-agent"]))
        self.assertEqual(resolve_mode_and_targets(parser.parse_args(["help"]))[0], "help")

        # 2. KeyboardInterrupt во время установки вызывает откат транзакции и пробрасывает KeyboardInterrupt
        sb_dir = os.path.join(self.test_dir, "ctrl_c_sb")
        ctx = ExecutionContext(non_interactive=True, sandbox=True, sandbox_os="debian", sandbox_dir=sb_dir)
        engine = Engine(context=ctx)
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)

        created_marker = os.path.join(sb_dir, "usr/local/bin/partial_file.sh")
        os.makedirs(os.path.dirname(created_marker), exist_ok=True)
        with open(created_marker, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
        engine.txn.record_created_file(created_marker)

        def interrupted_hook(*args, **kwargs):
            raise KeyboardInterrupt()

        engine.file_installer.install_file = interrupted_hook
        with self.assertRaises(KeyboardInterrupt):
            engine.install_packages(["vpn-agent"])

        # Файл, записанный в рамках прерванной транзакции, должен быть откачен (удален)
        self.assertFalse(os.path.exists(created_marker))


if __name__ == "__main__":
    unittest.main()


