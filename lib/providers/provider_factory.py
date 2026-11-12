"""
Factory for detecting and instantiating the appropriate EnvironmentProvider.
"""
import os
import platform
from typing import Optional
from lib.core.execution_context import ExecutionContext
from lib.providers.base_provider import BaseEnvironmentProvider
from lib.providers.linux_provider import LinuxProvider
from lib.providers.macos_provider import MacOSProvider
from lib.providers.sandbox_provider import SandboxProvider


class EnvironmentProviderFactory:
    """Фабрика создания провайдера окружения (LinuxProvider, MacOSProvider или SandboxProvider)."""

    @staticmethod
    def create(context: Optional[ExecutionContext] = None) -> BaseEnvironmentProvider:
        """
        Создает провайдер окружения:
        - Если передан флаг --sandbox (или переменная окружения DE_SANDBOX), создает SandboxProvider
          с имитацией выбранной ОС (context.sandbox_os).
        - На Darwin (macOS) создает MacOSProvider.
        - На Linux и прочих POSIX-системах создает LinuxProvider.
        """
        ctx = context or ExecutionContext()

        env_sandbox = os.getenv("DE_SANDBOX", "").strip().lower()
        if getattr(ctx, "sandbox", False) or (env_sandbox and env_sandbox not in ("0", "false", "no")):
            target_os = getattr(ctx, "sandbox_os", None) or (
                env_sandbox if env_sandbox not in ("1", "true", "yes") else "auto"
            )
            return SandboxProvider(context=ctx, sandbox_dir=getattr(ctx, "sandbox_dir", None), target_os=target_os)

        host_os = platform.system().lower()
        if host_os == "darwin":
            return MacOSProvider(context=ctx)

        return LinuxProvider(context=ctx)
