"""
Hook executor running pre- and post-install/uninstall commands.
"""
import subprocess
from typing import Optional
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.lifecycle.hook_context import HookContext


class HookExecutor:
    """Исполнитель хуков жизненного цикла пакета с поддержкой dry-run."""

    def __init__(self, context: Optional[ExecutionContext] = None):
        self.context = context or ExecutionContext()

    def run_hook(
        self,
        hook_name: str,
        command_or_script: Optional[str],
        pkg_name: str,
        pkg_dir: str = ".",
    ) -> bool:
        """
        Запускает хук (pre_install, post_install, pre_uninstall, post_uninstall).
        """
        if not command_or_script:
            return True

        hook_ctx = HookContext(pkg_name, pkg_dir)
        rendered_cmd = hook_ctx.render(command_or_script)

        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Выполнение хука {hook_name} для '{pkg_name}': {rendered_cmd}")
            return True

        self.context.log(f"⚙️ Выполнение {hook_name} ({pkg_name})...")
        try:
            res = subprocess.run(
                rendered_cmd,
                shell=True,
                check=True,
                cwd=pkg_dir,
            )
            return res.returncode == 0
        except subprocess.CalledProcessError as err:
            raise DeployEngineError(f"Сбой при выполнении хука {hook_name} для пакета '{pkg_name}': {err}")
