"""
Remote deployer managing packaging, transfer, and remote execution.
"""
import json
import os
import tarfile
import tempfile
from typing import Any, Dict, List, Optional
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.remote.ssh_client import SSHClient


class RemoteDeployer:
    """Удаленное развертывание и инспекция через SSH."""

    def __init__(self, target_host: str, context: Optional[ExecutionContext] = None):
        self.context = context or ExecutionContext()
        self.ssh_client = SSHClient(target_host)

    def fetch_remote_state(self) -> Dict[str, Any]:
        """Считывает /etc/default/state.json с удаленного хоста."""
        cmd = "cat /etc/default/state.json 2>/dev/null || echo '{\"installed\":{}}'"
        try:
            res = self.ssh_client.run_command(cmd, capture_output=True)
            return json.loads(res.stdout)
        except Exception as err:
            raise DeployEngineError(f"Не удалось получить состояние с удаленного хоста: {err}")

    def execute_remote(self, targets: List[str], action: str = "install") -> None:
        """
        Упаковывает текущий деплоер, передает его на удаленный хост и запускает deploy.py.
        """
        self.context.log(f"🚀 Подготовка удаленного деплоя на {self.ssh_client.target_host}...")

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_bundle:
            bundle_path = tmp_bundle.name

        try:
            # Создаем легковесный архив проекта (исключая .git, .venv, node_modules)
            with tarfile.open(bundle_path, "w:gz") as tar:
                def exclude_filter(tarinfo):
                    ignored = [".git", ".venv", "node_modules", "__pycache__", "dist"]
                    for ig in ignored:
                        if ig in tarinfo.name.split("/"):
                            return None
                    return tarinfo

                tar.add(".", arcname="deploy_engine", filter=exclude_filter)

            remote_archive = "/tmp/de_bundle.tar.gz"
            remote_dir = "/tmp/de_deploy_run"

            self.context.log(f"📤 Передача архива на {self.ssh_client.target_host}:{remote_archive}...")
            self.ssh_client.scp_file(bundle_path, remote_archive)

            # Формируем флаги CLI
            flags = []
            if self.context.dry_run:
                flags.append("--dry-run")
            if self.context.purge:
                flags.append("--purge")
            if self.context.clean_env:
                flags.append("--clean-env")
            flags_str = " ".join(flags)
            targets_str = " ".join(targets)

            remote_cmd = (
                f"rm -rf {remote_dir} && mkdir -p {remote_dir} && "
                f"tar -xzf {remote_archive} -C {remote_dir} && "
                f"cd {remote_dir}/deploy_engine && "
                f"sudo python3 deploy.py {action} {targets_str} {flags_str} && "
                f"rm -rf {remote_dir} {remote_archive}"
            )

            self.context.log("⚡ Выполнение развертывания на удаленном сервере...")
            self.ssh_client.run_command(remote_cmd, capture_output=False)
            self.context.log("✅ Удаленное выполнение успешно завершено.")

        finally:
            if os.path.exists(bundle_path):
                try:
                    os.remove(bundle_path)
                except OSError:
                    pass
