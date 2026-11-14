"""
Unit tests for cross-platform Environment Providers, SystemdToPlistConverter, OS compatibility filtering,
and Sandbox OS emulation (--sandbox [debian|macos]).
"""
import json
import os
import plistlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files"))

from lib.core.deploy_engine_error import DeployEngineError
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.providers.sandbox_provider import SandboxProvider
from lib.providers.systemd_to_plist_converter import SystemdToPlistConverter


class TestCrossPlatformProviders(unittest.TestCase):
    """Тесты кроссплатформенных провайдеров, конвертации systemd -> launchd plist и песочницы с выбором ОС."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_xplat_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_systemd_to_plist_converter_with_timer_and_static_env(self):
        """Проверка автоматической конвертации .service + .timer + .env в launchd XML .plist."""
        service_content = "[Unit]\nDescription=Sync Worker\n[Service]\nWorkingDirectory=/opt/de_sync-pkg/files\nEnvironment=\"LOG_LEVEL=info\"\nExecStart=/usr/local/bin/sync-worker.sh --daemon\nRestart=on-failure\n"
        timer_content = "[Unit]\nDescription=Run Sync Worker every 15 minutes\n[Timer]\nOnUnitActiveSec=15m\n"
        static_env = SystemdToPlistConverter.parse_env_text('API_TOKEN="secret_123"\nWORKER_PORT=8080\n')
        xml_str = SystemdToPlistConverter.convert_to_xml(
            pkg_name="sync-pkg", unit_name="sync-worker.service", service_text=service_content, timer_text=timer_content, env_vars=static_env
        )
        parsed = plistlib.loads(xml_str.encode("utf-8"))
        self.assertEqual(parsed["Label"], "com.deploy-engine.sync-pkg.sync-worker")
        self.assertEqual(parsed["ProgramArguments"], ["/usr/local/bin/sync-worker.sh", "--daemon"])
        self.assertEqual(parsed["WorkingDirectory"], "/opt/de_sync-pkg/files")
        self.assertEqual(parsed["StartInterval"], 900)
        self.assertEqual(parsed["EnvironmentVariables"]["API_TOKEN"], "secret_123")
        self.assertEqual(parsed["EnvironmentVariables"]["WORKER_PORT"], "8080")
        self.assertEqual(parsed["EnvironmentVariables"]["LOG_LEVEL"], "info")

    def test_platform_compatibility_and_dict_sys_packages(self):
        """Проверка фильтрации по platforms/os и словарного формата sys_packages для Debian и macOS."""
        sb_debian = SandboxProvider(sandbox_dir=os.path.join(self.test_dir, "sb_deb"), target_os="debian")
        sb_macos = SandboxProvider(sandbox_dir=os.path.join(self.test_dir, "sb_mac"), target_os="macos")

        universal_pkg = {"name": "uni-tool"}
        debian_only_pkg = {"name": "deb-kernel-mod", "platforms": ["debian", "ubuntu"]}
        macos_only_pkg = {"name": "mac-agent", "platforms": ["macos"]}

        self.assertTrue(sb_debian.is_package_compatible(universal_pkg))
        self.assertTrue(sb_macos.is_package_compatible(universal_pkg))

        self.assertTrue(sb_debian.is_package_compatible(debian_only_pkg))
        self.assertFalse(sb_macos.is_package_compatible(debian_only_pkg))

        self.assertFalse(sb_debian.is_package_compatible(macos_only_pkg))
        self.assertTrue(sb_macos.is_package_compatible(macos_only_pkg))

        sys_pkgs_spec = {
            "common": ["curl", "jq"],
            "apt": ["netcat-openbsd", "iproute2"],
            "brew": ["netcat", "iproute2mac"],
        }
        self.assertEqual(sb_debian.resolve_sys_packages(sys_pkgs_spec), ["curl", "jq", "netcat-openbsd", "iproute2"])
        self.assertEqual(sb_macos.resolve_sys_packages(sys_pkgs_spec), ["curl", "jq", "netcat", "iproute2mac"])

    def test_end_to_end_sandbox_macos_plist_generation_and_os_blocking(self):
        """
        Проверка полной установки пакета в песочнице с эмуляцией macOS (--sandbox macos):
        генерация .plist со статическими переменными из .env и блокировка Linux-only пакетов.
        """
        pkgs_root = os.path.join(self.test_dir, "repo")
        mac_pkg_dir = os.path.join(pkgs_root, "cross-daemon")
        deb_pkg_dir = os.path.join(pkgs_root, "debian-only")
        os.makedirs(mac_pkg_dir, exist_ok=True)
        os.makedirs(deb_pkg_dir, exist_ok=True)

        with open(os.path.join(mac_pkg_dir, "deploy.env"), "w") as f:
            f.write("DAEMON_PORT=9090\nDAEMON_MODE=active\n")
        with open(os.path.join(mac_pkg_dir, "daemon.sh"), "w") as f:
            f.write("#!/bin/sh\necho running\n")
        with open(os.path.join(mac_pkg_dir, "daemon.service"), "w") as f:
            f.write("[Service]\nExecStart={{SYS_BIN}}/daemon.sh --run\nRestart=always\n")
        with open(os.path.join(mac_pkg_dir, "daemon.timer"), "w") as f:
            f.write("[Timer]\nOnUnitActiveSec=5m\n")

        with open(os.path.join(mac_pkg_dir, "manifest.json"), "w") as f:
            json.dump(
                {
                    "name": "cross-daemon",
                    "platforms": ["linux", "macos"],
                    "sys_packages": {"common": ["curl"], "brew": ["jq"]},
                    "units": {
                        "deploy.env": {"type": "env"},
                        "daemon.sh": {"type": "script"},
                        "daemon.service": {"type": "unit"},
                        "daemon.timer": {"type": "timer"},
                    },
                    "post_install": ["systemctl daemon-reload", "systemctl enable --now daemon.service"],
                },
                f,
            )

        with open(os.path.join(deb_pkg_dir, "manifest.json"), "w") as f:
            json.dump({"name": "debian-only", "platforms": ["debian"], "units": {}}, f)

        sandbox_mac_dir = os.path.join(self.test_dir, "sandbox_macos")
        ctx = ExecutionContext(sandbox=True, sandbox_os="macos", sandbox_dir=sandbox_mac_dir)
        engine = Engine(ctx)
        engine.discover_packages(search_roots=[pkgs_root], force_rescan=True)

        # 1. Установка совместимого пакета в песочнице macOS должна скомпилировать .plist
        engine.install_packages(["cross-daemon"])
        expected_plist = os.path.join(
            sandbox_mac_dir, "Library", "LaunchDaemons", "com.deploy-engine.cross-daemon.daemon.plist"
        )
        self.assertTrue(os.path.isfile(expected_plist))

        with open(expected_plist, "rb") as pf:
            plist_data = plistlib.load(pf)
        self.assertEqual(plist_data["StartInterval"], 300)
        self.assertEqual(plist_data["EnvironmentVariables"]["DAEMON_PORT"], "9090")
        self.assertEqual(plist_data["EnvironmentVariables"]["DAEMON_MODE"], "active")

        # 2. Установка пакета только для Debian в окружении macOS должна блокироваться
        with self.assertRaises(DeployEngineError):
            engine.install_packages(["debian-only"])

    def test_local_env_preset_and_dynamic_environment_switch(self):
        """
        Проверка сохранения предустановки в ./env/<pkg>.env без модификации репозитория пакетов
        и динамического переключения окружения через Engine.configure_environment().
        """
        from lib.env.env_upsert_manager import EnvUpsertManager
        from lib.installer.transaction_manager import TransactionManager

        repo_template = os.path.join(self.test_dir, "repo_pkg", "deploy.env")
        os.makedirs(os.path.dirname(repo_template), exist_ok=True)
        original_template_content = (
            "# Основной порт сервиса\n"
            "SERVICE_PORT={{PROMPT:Введите порт:8080}}\n"
            "API_KEY={{PROMPT:Введите ключ API:default_key}}\n"
            "LOG_MODE=production\n"
        )
        with open(repo_template, "w", encoding="utf-8") as f:
            f.write(original_template_content)

        local_env_dir = os.path.join(self.test_dir, "local_env_store")
        env_mgr = EnvUpsertManager(
            ExecutionContext(non_interactive=True),
            TransactionManager(),
            local_env_dir=local_env_dir,
        )

        # 1. Чтение всех переменных для модального редактора TUI
        entries = env_mgr.parser.parse_editable_entries(repo_template)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["key"], "SERVICE_PORT")
        self.assertTrue(entries[0]["has_prompt"])
        self.assertEqual(entries[0]["default_value"], "8080")

        # 2. Сохранение пользовательской предустановки в папку local_env_store/my-service.env
        preset_file = env_mgr.save_local_preset(
            "my-service",
            repo_template,
            {"SERVICE_PORT": "9095", "API_KEY": "custom_secret_token", "LOG_MODE": "debug"},
        )
        self.assertTrue(os.path.isfile(preset_file))

        # Исходный шаблон в репозитории пакетов НЕ должен измениться
        with open(repo_template, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), original_template_content)

        # 3. При установке пакета upsert_env_file автоматически использует предустановку из ./env/ без вопросов
        dest_env = os.path.join(self.test_dir, "etc_default", "de_my-service", "my-service.env")
        env_mgr.upsert_env_file(repo_template, dest_env, pkg_name="my-service")
        with open(dest_env, "r", encoding="utf-8") as f:
            installed_env_text = f.read()
        self.assertIn("SERVICE_PORT=9095", installed_env_text)
        self.assertIn("API_KEY=custom_secret_token", installed_env_text)
        self.assertIn("LOG_MODE=debug", installed_env_text)
        self.assertNotIn("{{PROMPT:", installed_env_text)

        # 4. Проверка динамического переключения Sandbox/OS в Engine (для чекбокса и выпадающего списка TUI)
        engine = Engine(ExecutionContext(sandbox_dir=os.path.join(self.test_dir, "sb_dyn")))
        engine.configure_environment(sandbox=True, sandbox_os="alpine")
        self.assertTrue(engine.provider.is_sandbox)
        self.assertEqual(engine.provider.distro_id, "alpine")
        self.assertEqual(engine.provider.detect_package_manager(), "apk")

        engine.configure_environment(sandbox=True, sandbox_os="macos")
        self.assertEqual(engine.provider.os_family, "macos")
        self.assertTrue(engine.provider.uses_launchd_plist())

    def test_package_inspector_info_command_and_installed_paths(self):
        """Проверка работы инспектора пакета (info / --info): описание, категория и установленные пути."""
        from lib.state.package_inspector import PackageInspector

        cat_dir = os.path.join(self.test_dir, "net")
        pkg_dir = os.path.join(cat_dir, "dns-agent")
        os.makedirs(pkg_dir, exist_ok=True)

        with open(os.path.join(cat_dir, "category.json"), "w", encoding="utf-8") as f:
            json.dump({"desc": "Сетевые агенты"}, f)

        with open(os.path.join(pkg_dir, "agent.sh"), "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho ok\n")

        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({
                "name": "dns-agent",
                "desc": "Агент обновления DNS",
                "units": {"agent.sh": {"type": "script", "desc": "Основной скрипт агента"}},
            }, f)

        sb_dir = os.path.join(self.test_dir, "sb_info")
        ctx = ExecutionContext(sandbox=True, sandbox_os="debian", sandbox_dir=sb_dir)
        engine = Engine(ctx)
        engine.discover_packages(search_roots=[self.test_dir], force_rescan=True)
        engine.install_packages(["dns-agent"])

        inspector = PackageInspector(state_repo=engine.state_repo, engine=engine)
        info = inspector.get_package_info("dns-agent")
        self.assertIsNotNone(info)
        self.assertTrue(info["installed"])
        self.assertEqual(info["description"], "Агент обновления DNS")
        self.assertEqual(info["category"], "net")
        self.assertEqual(info["category_description"], "Сетевые агенты")
        self.assertEqual(info["files_count"], 1)
        self.assertTrue(info["files"][0]["exists"])
        self.assertIn("usr/local/bin/agent.sh", info["files"][0]["path"])

        formatted = inspector.format_package_info("dns-agent")
        self.assertIn("Агент обновления DNS", formatted)
        self.assertIn("Основной скрипт агента", formatted)

    def test_apt_cache_ttl_and_safe_uninstall_guards(self):
        """Проверка 60-минутного TTL кэша пакетов (apt/apk/pacman) и защиты от пустых путей/списков при удалении."""
        import time
        from lib.installer.file_installer import FileInstaller
        from lib.lifecycle.hook_executor import HookExecutor
        from lib.providers.linux_provider import LinuxProvider

        lp = LinuxProvider(ExecutionContext())
        apt_dir = os.path.join(self.test_dir, "apt_lists")
        os.makedirs(os.path.join(apt_dir, "partial"), exist_ok=True)
        open(os.path.join(apt_dir, "lock"), "w").close()
        stamp = os.path.join(self.test_dir, "apt.stamp")

        # 1. Только служебные lock/partial -> кэш считается пустым -> требуется update
        self.assertTrue(lp.needs_cache_update("apt-get", ttl_seconds=3600, cache_dir_override=apt_dir, stamp_path_override=stamp))

        # 2. Появился свежий индекс (< 60 мин) -> update НЕ требуется
        idx_file = os.path.join(apt_dir, "deb.debian.org_Packages")
        open(idx_file, "w").close()
        self.assertFalse(lp.needs_cache_update("apt-get", ttl_seconds=3600, cache_dir_override=apt_dir, stamp_path_override=stamp))

        # 3. Индекс старше 60 минут (4000 сек) -> требуется update
        old_ts = time.time() - 4000
        os.utime(idx_file, (old_ts, old_ts))
        self.assertTrue(lp.needs_cache_update("apt-get", ttl_seconds=3600, cache_dir_override=apt_dir, stamp_path_override=stamp))

        # 4. Защита от пустых переменных вида TEST_LIST_RM="" -> rm ${TEST_LIST_RM}/* и запрет rm во всех хуках манифеста
        for bad_path in ("", "   ", "/", "/*", "/opt/*", "/opt", "/etc/default", "/var/lib", "/opt/de_", "relative/path"):
            self.assertFalse(FileInstaller.is_safe_to_remove(bad_path), f"Должен блокироваться путь: {bad_path}")
        self.assertTrue(FileInstaller.is_safe_to_remove("/opt/de_my-pkg"))
        self.assertTrue(FileInstaller.is_safe_to_remove("/opt/de_my-pkg/files/main.py"))
        self.assertFalse(HookExecutor.is_safe_shell_command("rm -rf /*"))
        self.assertFalse(HookExecutor.is_safe_shell_command("echo start; rm /*"))
        self.assertFalse(HookExecutor.is_safe_shell_command("rm -f /tmp/somefile", disallow_all_rm=True))
        self.assertFalse(HookExecutor.is_safe_shell_command("echo 1 && sudo rm -rf /opt/de_test", disallow_all_rm=True))

        # 5. Защита Engine.uninstall_package от пустого имени, пустого списка удаления и блокировка rm в post_install
        engine = Engine(ExecutionContext(sandbox=True, sandbox_os="debian", sandbox_dir=os.path.join(self.test_dir, "sb_uninst")))
        with self.assertRaises(DeployEngineError):
            engine.uninstall_package("")
        self.assertFalse(engine.uninstall_package("nonexistent-pkg"))
        for hook_name in ("pre_install", "post_install", "pre_uninstall", "post_uninstall"):
            with self.assertRaises(DeployEngineError):
                engine.hook_executor.run_hook(hook_name, ["rm -rf /tmp/test"], "my-pkg")


if __name__ == "__main__":
    unittest.main()
