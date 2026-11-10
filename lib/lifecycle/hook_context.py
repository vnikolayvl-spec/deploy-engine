"""
Hook context and macro substitution engine.
"""
import os
from typing import Dict
from deploy_config import (
    DATA_PREFIX,
    ENV_PATH,
    ENV_PREFIX,
    STATE_DIR,
    SYS_BIN,
    SYS_SYSTEMD,
    VENV_PATH,
)


class HookContext:
    """Подстановка системных макросов в команды хуков."""

    def __init__(self, pkg_name: str, pkg_dir: str = "."):
        self.pkg_name = pkg_name
        self.pkg_dir = os.path.abspath(pkg_dir)

    def get_macros(self) -> Dict[str, str]:
        """Возвращает словарь системных переменных для интерполяции."""
        return {
            "{{SYS_BIN}}": SYS_BIN,
            "{{SYS_SYSTEMD}}": SYS_SYSTEMD,
            "{{ENV_PATH}}": ENV_PATH,
            "{{STATE_DIR}}": STATE_DIR,
            "{{VENV_PATH}}": VENV_PATH,
            "{{PKG_NAME}}": self.pkg_name,
            "{{PKG_DIR}}": self.pkg_dir,
            "{{ENV_DIR}}": os.path.join(ENV_PATH, f"{ENV_PREFIX}{self.pkg_name}"),
            "{{DATA_DIR}}": os.path.join(STATE_DIR, f"{DATA_PREFIX}{self.pkg_name}"),
        }

    def render(self, command: str) -> str:
        """Заменяет все макросы в строке команды."""
        macros = self.get_macros()
        rendered = command
        for macro, value in macros.items():
            rendered = rendered.replace(macro, value)
        return rendered
