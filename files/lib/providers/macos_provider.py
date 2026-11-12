"""
macOS (Darwin) Environment Provider supporting Homebrew/MacPorts and launchd (.plist).
"""
import os
import re
import shutil
import subprocess
from typing import Dict, List, Optional
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.providers.base_provider import BaseEnvironmentProvider
from lib.providers.systemd_to_plist_converter import SystemdToPlistConverter


class MacOSProvider(BaseEnvironmentProvider):
    """
    Нативный провайдер окружения для macOS (Darwin):
    - установка пакетов через Homebrew (brew) или MacPorts (port)
    - автоконвертация .service/.timer/.env в launchd .plist
    - адаптация сервисных вызовов systemctl -> launchctl
    """

    def __init__(self, context: Optional[ExecutionContext] = None):
        super().__init__(context)
        self.os_family = "macos"
        self.distro_id = "macos"
        self.distro_like = ["darwin", "bsd"]

    def detect_package_manager(self) -> Optional[str]:
        """Ищет brew или port в PATH и стандартных префиксах macOS."""
        for pm, extra_paths in (
            ("brew", ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]),
            ("port", ["/opt/local/bin/port"]),
        ):
            if shutil.which(pm):
                return pm
            for path in extra_paths:
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return pm
        return None

    def _get_pm_executable(self, pm: str) -> str:
        """Возвращает полный путь к исполняемому файлу пакетного менеджера."""
        found = shutil.which(pm)
        if found:
            return found
        candidates = {
            "brew": ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"],
            "port": ["/opt/local/bin/port"],
        }
        for c in candidates.get(pm, []):
            if os.path.isfile(c):
                return c
        return pm

    def get_paths(self) -> Dict[str, str]:
        """Возвращает нативные пути macOS с учетом прав текущего пользователя."""
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        home = os.path.expanduser("~")

        if os.path.isdir("/opt/homebrew/bin") and os.access("/opt/homebrew/bin", os.W_OK):
            sys_bin = "/opt/homebrew/bin"
        elif os.access("/usr/local/bin", os.W_OK) or is_root:
            sys_bin = "/usr/local/bin"
        else:
            sys_bin = os.path.join(home, ".local", "bin")

        if is_root:
            sys_systemd = "/Library/LaunchDaemons"
            env_path = "/etc/default"
            state_dir = "/var/lib"
            opt_dir = "/opt"
        else:
            sys_systemd = os.path.join(home, "Library", "LaunchAgents")
            env_path = os.path.join(home, ".config", "deploy-engine", "default")
            state_dir = os.path.join(home, ".local", "state", "deploy-engine")
            opt_dir = os.path.join(home, ".local", "opt")

        return {
            "sys_bin": sys_bin,
            "sys_systemd": sys_systemd,
            "env_path": env_path,
            "state_dir": state_dir,
            "opt_dir": opt_dir,
        }

    # Сопоставление пакетных имен с бинарниками, которые уже встроены в macOS или установлены
    MACOS_BUILTIN_BINARIES = {
        "tar": "tar",
        "curl": "curl",
        "git": "git",
        "python3": "python3",
        "python": "python3",
        "openssh-client": "ssh",
        "openssh-clients": "ssh",
        "openssh": "ssh",
        "rsync": "rsync",
    }
    LINUX_ONLY_PACKAGES = {
        "python3-venv",
        "python3-pip",
        "python3-full",
        "py3-pip",
        "python-pip",
        "ca-certificates",
    }

    def install_sys_packages(self, packages: List[str]) -> bool:
        """Устанавливает системные пакеты через Homebrew или MacPorts, пропуская встроенные утилиты macOS."""
        unique_pkgs = list(dict.fromkeys([p for p in packages if p]))
        if not unique_pkgs:
            return True

        pm = self.detect_package_manager()
        if self.context.dry_run:
            pm_label = pm or "brew"
            self.context.log(f"🔎 [DRY-RUN] Системные пакеты для установки ({pm_label}): {', '.join(unique_pkgs)}")
            return True

        already_present: List[str] = []
        to_install: List[str] = []
        for pkg in unique_pkgs:
            if pkg in self.LINUX_ONLY_PACKAGES:
                already_present.append(pkg)
                continue
            check_bin = self.MACOS_BUILTIN_BINARIES.get(pkg, pkg)
            if shutil.which(check_bin):
                already_present.append(pkg)
            else:
                to_install.append(pkg)

        if already_present:
            self.context.log(f"✅ Системные зависимости уже присутствуют в macOS: {', '.join(already_present)}")
        if not to_install:
            return True

        if not pm:
            self.context.log(
                f"⚠️ Пакетный менеджер macOS (brew/port) не найден. Пропуск системных пакетов: {', '.join(to_install)}"
            )
            return True

        pm_bin = self._get_pm_executable(pm)
        self.context.log(f"🍺 Установка {len(to_install)} системных пакетов на macOS через {pm}...")
        self.context.log(f"   Пакеты: {', '.join(to_install)}")

        if pm == "brew":
            # Homebrew не допускает запуск от root: если запущено через sudo, выполняем от SUDO_USER
            sudo_user = os.environ.get("SUDO_USER")
            if hasattr(os, "geteuid") and os.geteuid() == 0 and sudo_user:
                cmd = ["sudo", "-u", sudo_user, pm_bin, "install"] + to_install
            else:
                cmd = [pm_bin, "install"] + to_install
        else:
            cmd = [pm_bin, "install"] + to_install

        try:
            res = subprocess.run(cmd, check=True)
            return res.returncode == 0
        except subprocess.CalledProcessError as err:
            raise DeployEngineError(f"Ошибка при установке пакетов через {pm} ({to_install}): {err}")

    def translate_hook_command(self, command: str, pkg_name: str = "") -> str:
        """Автоматически транслирует команды systemctl в вызовы launchctl для .plist на macOS."""
        cmd = command.strip()
        if "systemctl" not in cmd:
            return command

        if re.match(r"^systemctl\s+daemon-reload\b", cmd):
            return "true"

        paths = self.get_paths()
        launch_dir = paths["sys_systemd"]

        # Ищем упоминание юнита .service или .timer в команде systemctl
        unit_match = re.search(r"([a-zA-Z0-9_.@-]+\.(?:service|timer))", cmd)
        if unit_match and pkg_name:
            unit_name = unit_match.group(1)
            plist_file = SystemdToPlistConverter.get_plist_filename(pkg_name, unit_name)
            plist_path = os.path.join(launch_dir, plist_file)
            if any(act in cmd for act in ("enable", "start", "restart")):
                return (
                    f"launchctl unload '{plist_path}' 2>/dev/null || true; "
                    f"launchctl load -w '{plist_path}' 2>/dev/null || true"
                )
            if any(act in cmd for act in ("disable", "stop")):
                return f"launchctl unload -w '{plist_path}' 2>/dev/null || true"

        return "true"

    def requires_root(self) -> bool:
        """На macOS допускается работа как в пространстве пользователя (LaunchAgents + brew), так и под root."""
        return False
