"""
Hook context and macro substitution engine with EnvironmentProvider path support.
"""
import os
from typing import Dict, Optional
from deploy_config import (
    DATA_PREFIX,
    ENV_PATH,
    ENV_PREFIX,
    STATE_DIR,
    SYS_BIN,
    SYS_SYSTEMD,
    VENV_PATH,
)
from lib.providers.base_provider import BaseEnvironmentProvider


class HookContext:
    """Подстановка системных макросов в команды хуков с учетом активного провайдера окружения."""

    def __init__(
        self,
        pkg_name: str,
        pkg_dir: str = ".",
        provider: Optional[BaseEnvironmentProvider] = None,
    ):
        self.pkg_name = pkg_name
        self.pkg_dir = os.path.abspath(pkg_dir)
        self.provider = provider

    def get_macros(self) -> Dict[str, str]:
        """Возвращает словарь системных переменных для интерполяции."""
        paths = (
            self.provider.get_paths()
            if self.provider
            else {
                "sys_bin": SYS_BIN,
                "sys_systemd": SYS_SYSTEMD,
                "env_path": ENV_PATH,
                "state_dir": STATE_DIR,
            }
        )
        env_base = paths["env_path"]
        state_base = paths["state_dir"]
        return {
            "{{SYS_BIN}}": paths["sys_bin"],
            "{{SYS_SYSTEMD}}": paths["sys_systemd"],
            "{{ENV_PATH}}": env_base,
            "{{STATE_DIR}}": state_base,
            "{{VENV_PATH}}": VENV_PATH,
            "{{PKG_NAME}}": self.pkg_name,
            "{{PKG_DIR}}": self.pkg_dir,
            "{{BASE_DIR}}": self.pkg_dir,
            "{{ROOT_DIR}}": os.path.dirname(self.pkg_dir),
            "{{ENV_DIR}}": os.path.join(env_base, f"{ENV_PREFIX}{self.pkg_name}"),
            "{{DATA_DIR}}": os.path.join(state_base, f"{DATA_PREFIX}{self.pkg_name}"),
        }

    def render(self, command: str) -> str:
        """Заменяет все макросы в строке команды и адаптирует сервисные вызовы под ОС."""
        macros = self.get_macros()
        rendered = str(command)
        for macro, value in macros.items():
            rendered = rendered.replace(macro, value)
        if self.provider:
            rendered = self.provider.translate_hook_command(rendered, self.pkg_name)
        return rendered
