"""
Sandbox Environment Provider for isolated testing and cross-OS simulation (--sandbox [target_os]).
"""
import os
import platform
from typing import Dict, List, Optional
from lib.core.execution_context import ExecutionContext
from lib.providers.base_provider import BaseEnvironmentProvider


class SandboxProvider(BaseEnvironmentProvider):
    """
    Тестовый провайдер локальной песочницы (--sandbox [target_os]).
    Позволяет эмулировать целевую ОС (например, debian, ubuntu, alpine, arch или macos)
    внутри изолированной директории без прав root и без модификации хост-системы.
    """

    DISTRO_PM_MAP = {
        "debian": ("linux", "apt-get", ["debian"]),
        "ubuntu": ("linux", "apt-get", ["debian"]),
        "linux": ("linux", "apt-get", ["debian"]),
        "fedora": ("linux", "dnf", ["rhel", "fedora"]),
        "rhel": ("linux", "dnf", ["rhel", "fedora"]),
        "centos": ("linux", "yum", ["rhel", "fedora"]),
        "alpine": ("linux", "apk", ["alpine"]),
        "arch": ("linux", "pacman", ["arch"]),
        "macos": ("macos", "brew", ["darwin", "bsd"]),
        "darwin": ("macos", "brew", ["darwin", "bsd"]),
        "osx": ("macos", "brew", ["darwin", "bsd"]),
    }

    SHIM_BINARIES = (
        "systemctl",
        "launchctl",
        "apt-get",
        "brew",
        "ufw",
        "iptables",
        "ip",
        "certbot",
        "nginx",
        "needrestart",
    )

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        sandbox_dir: Optional[str] = None,
        target_os: Optional[str] = None,
    ):
        super().__init__(context)
        self.is_sandbox = True
        raw_dir = sandbox_dir or getattr(self.context, "sandbox_dir", None) or os.getenv("DE_SANDBOX_DIR", "./.de_sandbox")
        self.sandbox_dir = os.path.abspath(raw_dir)

        requested_os = (target_os or getattr(self.context, "sandbox_os", None) or "auto").strip().lower()
        if requested_os in ("auto", "", "true", "1"):
            host_sys = platform.system().lower()
            requested_os = "macos" if host_sys == "darwin" else "debian"

        os_family, pm_name, distro_like = self.DISTRO_PM_MAP.get(
            requested_os, ("linux", "apt-get", ["debian"])
        )
        self.os_family = os_family
        self.distro_id = "macos" if os_family == "macos" else requested_os
        self.distro_like = list(distro_like)
        self._emulated_pm = pm_name

    def detect_package_manager(self) -> Optional[str]:
        """Возвращает эмулируемый пакетный менеджер для выбранной в песочнице ОС."""
        return self._emulated_pm

    def get_paths(self) -> Dict[str, str]:
        """Возвращает изолированные пути внутри директории песочницы в соответствии с эмулируемой ОС."""
        root = self.sandbox_dir or os.path.abspath("./.de_sandbox")
        if self.os_family == "macos":
            return {
                "sys_bin": os.path.join(root, "opt", "homebrew", "bin"),
                "sys_systemd": os.path.join(root, "Library", "LaunchDaemons"),
                "env_path": os.path.join(root, "etc", "default"),
                "state_dir": os.path.join(root, "var", "lib"),
                "opt_dir": os.path.join(root, "opt"),
            }
        return {
            "sys_bin": os.path.join(root, "usr", "local", "bin"),
            "sys_systemd": os.path.join(root, "etc", "systemd", "system"),
            "env_path": os.path.join(root, "etc", "default"),
            "state_dir": os.path.join(root, "var", "lib"),
            "opt_dir": os.path.join(root, "opt"),
        }

    def _ensure_shims(self) -> str:
        """Создает исполняемые шим-скрипты в <sandbox>/.shims для безопасного прохождения хуков в тестах."""
        root = self.sandbox_dir or os.path.abspath("./.de_sandbox")
        shims_dir = os.path.join(root, ".shims")
        os.makedirs(shims_dir, exist_ok=True)
        log_file = os.path.join(root, "sandbox.log")

        for binary in self.SHIM_BINARIES:
            shim_path = os.path.join(shims_dir, binary)
            if not os.path.exists(shim_path):
                script = (
                    "#!/bin/sh\n"
                    f'echo "[SANDBOX-SHIM:{self.distro_id}] {binary} $*" >> "{log_file}"\n'
                    "exit 0\n"
                )
                with open(shim_path, "w", encoding="utf-8") as f:
                    f.write(script)
                os.chmod(shim_path, 0o755)
        return shims_dir

    def install_sys_packages(self, packages: List[str]) -> bool:
        """Фиксирует установку системных пакетов в журнале песочницы без обращения к хост-системе."""
        unique_pkgs = list(dict.fromkeys([p for p in packages if p]))
        if not unique_pkgs:
            return True

        pm = self.detect_package_manager() or "pkg"
        if self.context.dry_run:
            self.context.log(
                f"🔎 [DRY-RUN][SANDBOX:{self.distro_id}] Системные пакеты ({pm}): {', '.join(unique_pkgs)}"
            )
            return True

        root = self.sandbox_dir or os.path.abspath("./.de_sandbox")
        os.makedirs(root, exist_ok=True)
        pkg_log = os.path.join(root, "installed_sys_packages.txt")
        with open(pkg_log, "a", encoding="utf-8") as f:
            for pkg in unique_pkgs:
                f.write(f"{self.distro_id}:{pm}:{pkg}\n")

        self.context.log(
            f"🛡️ [SANDBOX:{self.distro_id}] Имитация установки пакетов через {pm}: {', '.join(unique_pkgs)}"
        )
        return True

    def translate_hook_command(self, command: str, pkg_name: str = "") -> str:
        """При эмуляции macOS транслирует команды systemctl в вызовы launchctl."""
        if self.os_family == "macos" and "systemctl" in command:
            from lib.providers.macos_provider import MacOSProvider
            mac_helper = MacOSProvider(self.context)
            mac_helper.get_paths = self.get_paths  # type: ignore[method-assign]
            return mac_helper.translate_hook_command(command, pkg_name)
        return command

    def get_hook_env(self) -> Dict[str, str]:
        """Добавляет каталог шимов и sys_bin песочницы в начало PATH для хуков."""
        env = dict(os.environ)
        paths = self.get_paths()
        if not self.context.dry_run:
            shims_dir = self._ensure_shims()
            env["PATH"] = f"{shims_dir}:{paths['sys_bin']}:{env.get('PATH', '')}"
        env["DE_SANDBOX_DIR"] = self.sandbox_dir or ""
        env["DE_SANDBOX_OS"] = self.distro_id
        return env

    def requires_root(self) -> bool:
        """Песочница никогда не требует прав root."""
        return False
