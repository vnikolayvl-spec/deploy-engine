"""
Hook executor running pre- and post-install/uninstall commands with cross-platform provider support.
"""
import re
import subprocess
from typing import List, Optional, Union
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.lifecycle.hook_context import HookContext
from lib.providers.base_provider import BaseEnvironmentProvider


class HookExecutor:
    """Исполнитель хуков жизненного цикла пакета с поддержкой провайдера окружения и полным запретом rm."""

    MANIFEST_HOOKS = {"pre_install", "post_install", "pre_uninstall", "post_uninstall"}

    # Запрет вызова rm в любых хуках манифеста (pre_install, post_install, pre_uninstall, post_uninstall)
    FORBIDDEN_RM_IN_HOOK_PATTERN = re.compile(
        r"(?:^|[;&|()`]\s*|\$\(\s*)(?:sudo\s+)?(?:/bin/rm|/usr/bin/rm|rm)(?:\s+|$)"
    )

    # Защита внутренних сервисных команд от удаления корня (rm /* или rm /)
    DANGEROUS_RM_PATTERN = re.compile(
        r"(?:^|[;&|]\s*)rm\s+(?:-[a-zA-Z0-9-]+\s+)*(?:['\"]?/\*['\"]?|['\"]?/['\"]?(?:\s|$|[;&|]))"
    )

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        provider: Optional[BaseEnvironmentProvider] = None,
    ):
        self.context = context or ExecutionContext()
        self.provider = provider

    @classmethod
    def is_safe_shell_command(cls, rendered_cmd: str, disallow_all_rm: bool = False) -> bool:
        """
        Проверяет безопасность shell-команды:
        - всегда блокирует удаление корня (rm /* или rm /);
        - при disallow_all_rm=True (для хуков манифеста) полностью запрещает команду rm.
        """
        if not rendered_cmd or not rendered_cmd.strip():
            return False
        if cls.DANGEROUS_RM_PATTERN.search(rendered_cmd):
            return False
        if disallow_all_rm and cls.FORBIDDEN_RM_IN_HOOK_PATTERN.search(rendered_cmd):
            return False
        return True

    def run_hook(
        self,
        hook_name: str,
        command_or_script: Optional[Union[str, List[str]]],
        pkg_name: str,
        pkg_dir: str = ".",
    ) -> bool:
        """
        Запускает хук (pre_install, post_install, pre_uninstall, post_uninstall).
        В хуках манифеста использование команды rm запрещено.
        """
        if not command_or_script:
            return True

        clean_pkg = (pkg_name or "").strip()
        if not clean_pkg:
            raise DeployEngineError(f"Невозможно выполнить хук {hook_name}: пустое имя пакета.")

        commands: List[str] = (
            command_or_script
            if isinstance(command_or_script, list)
            else [str(command_or_script)]
        )
        hook_ctx = HookContext(clean_pkg, pkg_dir, provider=self.provider)
        hook_env = self.provider.get_hook_env() if self.provider else None
        is_manifest_hook = hook_name in self.MANIFEST_HOOKS

        for cmd_tpl in commands:
            if not cmd_tpl or not str(cmd_tpl).strip():
                continue
            rendered_cmd = hook_ctx.render(str(cmd_tpl))

            if not self.is_safe_shell_command(rendered_cmd, disallow_all_rm=is_manifest_hook):
                raise DeployEngineError(
                    f"Запрещено использование команды 'rm' в хуке {hook_name} пакета '{clean_pkg}': {rendered_cmd}"
                )

            if self.context.dry_run:
                self.context.log(f"🔎 [DRY-RUN] Выполнение хука {hook_name} для '{clean_pkg}': {rendered_cmd}")
                continue

            self.context.log(f"⚙️ Выполнение {hook_name} ({clean_pkg}): {rendered_cmd}")
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
                raise DeployEngineError(f"Сбой при выполнении хука {hook_name} для пакета '{clean_pkg}': {err}")

        return True
