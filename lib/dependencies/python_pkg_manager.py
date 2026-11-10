"""
Python package manager for pip and virtualenv dependencies.
"""
import os
import shutil
import subprocess
from typing import List, Optional
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext


class PythonPackageManager:
    """Установка Python зависимостей (pip / requirements.txt) в виртуальное окружение или систему."""

    def __init__(self, venv_path: Optional[str] = None, context: Optional[ExecutionContext] = None):
        self.venv_path = venv_path or "./.venv"
        self.context = context or ExecutionContext()

    def get_pip_binary(self) -> str:
        """Определяет исполняемый файл pip (из venv или системный)."""
        if self.venv_path:
            venv_pip = os.path.join(self.venv_path, "bin", "pip")
            if os.path.exists(venv_pip):
                return venv_pip
        sys_pip = shutil.which("pip3") or shutil.which("pip")
        return sys_pip or "pip3"

    def install(self, packages: List[str], base_dir: Optional[str] = None) -> bool:
        """
        Устанавливает список Python пакетов или файлы requirements.txt.
        """
        if not packages:
            return True

        pip_bin = self.get_pip_binary()
        for item in packages:
            if item.endswith(".txt"):
                req_path = os.path.join(base_dir, item) if base_dir else item
                if self.context.dry_run:
                    self.context.log(f"🔎 [DRY-RUN] Установка Python requirements: {req_path}")
                    continue
                self.context.log(f"🐍 Установка Python зависимостей из {req_path}...")
                cmd = [pip_bin, "install", "-r", req_path]
            else:
                if self.context.dry_run:
                    self.context.log(f"🔎 [DRY-RUN] Установка Python пакета: {item}")
                    continue
                self.context.log(f"🐍 Установка Python пакета {item}...")
                cmd = [pip_bin, "install", item]

            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as err:
                raise DeployEngineError(f"Ошибка при установке Python зависимости '{item}': {err}")
        return True
