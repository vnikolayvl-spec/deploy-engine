"""
Node.js and npm package manager.
"""
import os
import shutil
import subprocess
from typing import List, Optional
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext


class NodePackageManager:
    """Установка Node.js / npm зависимостей."""

    def __init__(self, context: Optional[ExecutionContext] = None):
        self.context = context or ExecutionContext()

    def get_npm_binary(self) -> str:
        """Находит путь к npm."""
        npm_bin = shutil.which("npm")
        if not npm_bin:
            raise DeployEngineError("npm не найден в системе. Убедитесь, что Node.js установлен.")
        return npm_bin

    def install(self, packages: List[str], base_dir: Optional[str] = None) -> bool:
        """Устанавливает npm пакеты или запускает npm install в директории с package.json."""
        if not packages:
            return True

        npm_bin = self.get_npm_binary()
        for item in packages:
            if item == "package.json":
                work_dir = base_dir or "."
                if self.context.dry_run:
                    self.context.log(f"🔎 [DRY-RUN] npm install в {work_dir}")
                    continue
                self.context.log(f"📦 Запуск npm install в {work_dir}...")
                cmd = [npm_bin, "install", "--production"]
                cwd = work_dir
            else:
                if self.context.dry_run:
                    self.context.log(f"🔎 [DRY-RUN] npm install -g {item}")
                    continue
                self.context.log(f"📦 Установка npm пакета: {item}...")
                cmd = [npm_bin, "install", "-g", item]
                cwd = None

            try:
                subprocess.run(cmd, cwd=cwd, check=True)
            except subprocess.CalledProcessError as err:
                raise DeployEngineError(f"Ошибка npm при установке '{item}': {err}")
        return True
