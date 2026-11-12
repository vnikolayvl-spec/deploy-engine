"""
Linux Environment Provider supporting Debian/Ubuntu (apt), RHEL/Fedora (dnf/yum), Alpine (apk), and Arch (pacman).
"""
import os
import shutil
import subprocess
from typing import Dict, List, Optional
from deploy_config import ENV_PATH, STATE_DIR, SYS_BIN, SYS_SYSTEMD
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.providers.base_provider import BaseEnvironmentProvider


class LinuxProvider(BaseEnvironmentProvider):
    """Провайдер окружения для дистрибутивов Linux (systemd + apt/dnf/yum/apk/pacman)."""

    def __init__(self, context: Optional[ExecutionContext] = None):
        super().__init__(context)
        self.os_family = "linux"
        self.distro_id, self.distro_like = self._detect_linux_distro()

    @staticmethod
    def _detect_linux_distro() -> tuple[str, List[str]]:
        """Определяет ID и ID_LIKE дистрибутива Linux из /etc/os-release."""
        distro_id = "linux"
        distro_like: List[str] = []
        os_release_path = "/etc/os-release"
        if os.path.isfile(os_release_path):
            try:
                with open(os_release_path, "r", encoding="utf-8") as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if line.startswith("ID="):
                            distro_id = line.split("=", 1)[1].strip('"\'').lower()
                        elif line.startswith("ID_LIKE="):
                            raw_like = line.split("=", 1)[1].strip('"\'').lower()
                            distro_like = [x.strip() for x in raw_like.split() if x.strip()]
            except Exception:
                pass
        return distro_id, distro_like

    def detect_package_manager(self) -> Optional[str]:
        """Определяет доступный пакетный менеджер Linux."""
        for pm in ("apt-get", "dnf", "yum", "apk", "pacman"):
            if shutil.which(pm):
                return pm
        return None

    def get_paths(self) -> Dict[str, str]:
        """Возвращает стандартные системные пути Linux."""
        return {
            "sys_bin": SYS_BIN,
            "sys_systemd": SYS_SYSTEMD,
            "env_path": ENV_PATH,
            "state_dir": STATE_DIR,
            "opt_dir": "/opt",
        }

    def install_sys_packages(self, packages: List[str]) -> bool:
        """Устанавливает системные пакеты через обнаруженный пакетный менеджер Linux."""
        unique_pkgs = list(dict.fromkeys([p for p in packages if p]))
        if not unique_pkgs:
            return True

        pm = self.detect_package_manager()
        if self.context.dry_run:
            pm_label = pm or "apt-get"
            self.context.log(f"🔎 [DRY-RUN] Системные пакеты для установки ({pm_label}): {', '.join(unique_pkgs)}")
            return True

        if not pm:
            raise DeployEngineError(
                f"Системный пакетный менеджер (apt-get/dnf/yum/apk/pacman) не найден для установки: {unique_pkgs}"
            )

        self.context.log(f"📦 Установка {len(unique_pkgs)} системных пакетов через {pm}...")
        self.context.log(f"   Пакеты: {', '.join(unique_pkgs)}")

        if pm == "apt-get":
            cmd = ["apt-get", "install", "-y", "--no-install-recommends"] + unique_pkgs
        elif pm in ("dnf", "yum"):
            cmd = [pm, "install", "-y"] + unique_pkgs
        elif pm == "apk":
            cmd = ["apk", "add", "--no-cache"] + unique_pkgs
        elif pm == "pacman":
            cmd = ["pacman", "-S", "--noconfirm"] + unique_pkgs
        else:
            cmd = [pm, "install", "-y"] + unique_pkgs

        try:
            res = subprocess.run(cmd, check=True)
            return res.returncode == 0
        except subprocess.CalledProcessError as err:
            raise DeployEngineError(f"Ошибка при установке системных пакетов {unique_pkgs}: {err}")
        except FileNotFoundError:
            raise DeployEngineError(f"Пакетный менеджер {pm} не найден в системе.")
