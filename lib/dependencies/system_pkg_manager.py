"""
System package manager for aggregating and installing OS dependencies.
"""
import shutil
import subprocess
from typing import List, Optional
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext


class SystemPackageManager:
    """Агрегация и установка системных пакетов ОС за один вызов пакетного менеджера."""

    def __init__(self, context: Optional[ExecutionContext] = None):
        self.context = context or ExecutionContext()

    def detect_manager(self) -> str:
        """Определяет доступный системный пакетный менеджер."""
        for pm in ["apt-get", "dnf", "yum", "apk", "pacman"]:
            if shutil.which(pm):
                return pm
        return "apt-get"

    def install_packages(self, packages: List[str]) -> bool:
        """
        Агрегирует и устанавливает список системных пакетов.
        Если context.dry_run=True, только имитирует установку.
        """
        if not packages:
            return True

        # Убираем дубликаты с сохранением порядка
        unique_pkgs = list(dict.fromkeys(packages))
        pm = self.detect_manager()

        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Системные пакеты для установки ({pm}): {', '.join(unique_pkgs)}")
            return True

        self.context.log(f"📦 Установка {len(unique_pkgs)} системных пакетов через {pm}...")
        self.context.log(f"   Пакеты: {', '.join(unique_pkgs)}")

        cmd: List[str] = []
        if pm == "apt-get":
            cmd = ["apt-get", "install", "-y", "--no-install-recommends"] + unique_pkgs
        elif pm in ["dnf", "yum"]:
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
