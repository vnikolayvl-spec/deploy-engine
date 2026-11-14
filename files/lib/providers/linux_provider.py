"""
Linux Environment Provider supporting Debian/Ubuntu (apt), RHEL/Fedora (dnf/yum), Alpine (apk), and Arch (pacman).
"""
import os
import shutil
import subprocess
import time
from typing import Dict, List, Optional
from lib.config import ENV_PATH, STATE_DIR, SYS_BIN, SYS_SYSTEMD
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.providers.base_provider import BaseEnvironmentProvider


class LinuxProvider(BaseEnvironmentProvider):
    """Провайдер окружения для дистрибутивов Linux (systemd + apt/dnf/yum/apk/pacman)."""

    CACHE_TTL_SECONDS = 3600  # 60 минут

    PACKAGE_CACHE_DIRS = {
        "apt-get": "/var/lib/apt/lists",
        "apk": "/var/cache/apk",
        "pacman": "/var/lib/pacman/sync",
        "dnf": "/var/cache/dnf",
        "yum": "/var/cache/yum",
    }

    APT_IGNORED_ENTRIES = {"lock", "partial", "auxfiles"}

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

    @staticmethod
    def _get_stamp_path(pm: str) -> str:
        """Возвращает путь к файлу-метке последнего обновления индекса пакетов."""
        safe_pm = pm.replace("/", "_").strip() or "pkg"
        return f"/var/tmp/de_pkg_update_{safe_pm}.stamp"

    def needs_cache_update(
        self,
        pm: str,
        ttl_seconds: int = CACHE_TTL_SECONDS,
        cache_dir_override: Optional[str] = None,
        stamp_path_override: Optional[str] = None,
    ) -> bool:
        """
        Проверяет, нужно ли обновлять кэш пакетного менеджера:
        возвращает True, если кэш пуст или с прошлого обновления прошло более ttl_seconds (60 минут).
        """
        cache_dir = cache_dir_override or self.PACKAGE_CACHE_DIRS.get(pm, "")
        stamp_path = stamp_path_override or self._get_stamp_path(pm)

        if not cache_dir or not os.path.isdir(cache_dir):
            return True

        valid_files: List[str] = []
        try:
            for entry in os.listdir(cache_dir):
                if pm == "apt-get" and entry in self.APT_IGNORED_ENTRIES:
                    continue
                if entry.startswith("."):
                    continue
                full_p = os.path.join(cache_dir, entry)
                if os.path.isfile(full_p):
                    valid_files.append(full_p)
                elif pm in ("dnf", "yum") and os.path.isdir(full_p):
                    valid_files.append(full_p)
        except OSError:
            return True

        # Если в каталоге кэша нет ни одного файла индекса — кэш пуст, требуется update
        if not valid_files:
            return True

        latest_mtime = 0.0
        for fp in valid_files:
            try:
                mtime = os.path.getmtime(fp)
                if mtime > latest_mtime:
                    latest_mtime = mtime
            except OSError:
                continue

        if stamp_path and os.path.isfile(stamp_path):
            try:
                stamp_mtime = os.path.getmtime(stamp_path)
                if stamp_mtime > latest_mtime:
                    latest_mtime = stamp_mtime
            except OSError:
                pass

        if latest_mtime <= 0:
            return True

        age_seconds = time.time() - latest_mtime
        return age_seconds > ttl_seconds

    def _touch_stamp(self, stamp_path: str) -> None:
        """Обновляет временную метку успешного обновления кэша пакетного менеджера."""
        try:
            os.makedirs(os.path.dirname(stamp_path), exist_ok=True)
            with open(stamp_path, "w", encoding="utf-8") as f:
                f.write(str(int(time.time())))
        except OSError:
            pass

    def _ensure_package_cache_updated(self, pm: str, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        """Выполняет обновление кэша пакетов (apt-get update и аналоги), если кэш пуст или старше 60 минут."""
        if not self.needs_cache_update(pm, ttl_seconds=ttl_seconds):
            self.context.log(f"⚡ Кэш {pm} актуален (обновлен менее 60 мин. назад), пропуск обновления индекса.")
            return

        if pm == "apt-get":
            update_cmd = ["apt-get", "update", "-y"]
        elif pm == "apk":
            update_cmd = ["apk", "update"]
        elif pm == "pacman":
            update_cmd = ["pacman", "-Sy", "--noconfirm"]
        elif pm in ("dnf", "yum"):
            update_cmd = [pm, "makecache", "-y"]
        else:
            return

        self.context.log(f"🔄 Обновление индекса пакетов ({' '.join(update_cmd)})...")
        try:
            subprocess.run(update_cmd, check=True)
            self._touch_stamp(self._get_stamp_path(pm))
        except subprocess.CalledProcessError as err:
            raise DeployEngineError(f"Ошибка при обновлении индекса пакетов ({' '.join(update_cmd)}): {err}")

    def install_sys_packages(self, packages: List[str]) -> bool:
        """Устанавливает системные пакеты через обнаруженный пакетный менеджер Linux."""
        unique_pkgs = list(dict.fromkeys([p.strip() for p in packages if p and str(p).strip()]))
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

        self._ensure_package_cache_updated(pm)

        self.context.log(f"📦 Установка {len(unique_pkgs)} системных пакетов через {pm}...")
        self.context.log(f"   Пакеты: {', '.join(unique_pkgs)}")

        if pm == "apt-get":
            cmd = ["apt-get", "install", "-y", "--no-install-recommends"] + unique_pkgs
        elif pm in ("dnf", "yum"):
            cmd = [pm, "install", "-y"] + unique_pkgs
        elif pm == "apk":
            cmd = ["apk", "add"] + unique_pkgs
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
