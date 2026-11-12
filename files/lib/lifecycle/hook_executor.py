"""
Hook executor running pre- and post-install/uninstall commands with cross-platform provider support.
"""
import subprocess
from typing import List, Optional, Union
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.lifecycle.hook_context import HookContext
from lib.providers.base_provider import BaseEnvironmentProvider


class HookExecutor:
    """Исполнитель хуков жизненного цикла пакета с поддержкой провайдера окружения и dry-run."""

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        provider: Optional[BaseEnvironmentProvider] = None,
    ):
        self.context = context or ExecutionContext()
        self.provider = provider

    def run_hook(
        self,
        hook_name: str,
        command_or_script: Optional[Union[str, List[str]]],
        pkg_name: str,
        pkg_dir: str = ".",
    ) -> bool:
        """
        Запускает хук (pre_install, post_install, pre_uninstall, post_uninstall).
        Поддерживает одиночную команду (str) и массив команд (List[str]).
        """
        if not command_or_script:
            return True

        commands: List[str] = (
            command_or_script
            if isinstance(command_or_script, list)
            else [str(command_or_script)]
        )
        hook_ctx = HookContext(pkg_name, pkg_dir, provider=self.provider)
        hook_env = self.provider.get_hook_env() if self.provider else None

        for cmd_tpl in commands:
            if not cmd_tpl:
                continue
            rendered_cmd = hook_ctx.render(cmd_tpl)

            if self.context.dry_run:
                self.context.log(f"🔎 [DRY-RUN] Выполнение хука {hook_name} для '{pkg_name}': {rendered_cmd}")
                continue

            self.context.log(f"⚙️ Выполнение {hook_name} ({pkg_name}): {rendered_cmd}")
            try:
                res = subprocess.run(
                    rendered_cmd,
                    shell=True,
                    check=True,
                    cwd=pkg_dir,
                    env=hook_env,
                )
                if res.returncode != 0:
                    return False
            except subprocess.CalledProcessError as err:
                raise DeployEngineError(f"Сбой при выполнении хука {hook_name} для пакета '{pkg_name}': {err}")

        return True
