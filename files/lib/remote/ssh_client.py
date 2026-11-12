"""
SSH client for remote deployment and status querying.
"""
import shutil
import subprocess
from typing import List, Optional, Tuple
from lib.core.deploy_engine_error import DeployEngineError


class SSHClient:
    """Клиент для выполнения команд и передачи файлов по SSH."""

    def __init__(self, target_host: str, identity_file: Optional[str] = None):
        self.target_host = target_host
        self.identity_file = identity_file
        self.user, self.host, self.port = self._parse_target(target_host)

    def _parse_target(self, target: str) -> Tuple[Optional[str], str, int]:
        """Парсит строку вида [user@]host[:port]."""
        port = 22
        user = None

        if "@" in target:
            user, host_part = target.split("@", 1)
        else:
            host_part = target

        if ":" in host_part:
            host, port_str = host_part.split(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 22
        else:
            host = host_part

        return user, host, port

    def _build_ssh_cmd(self, command: str) -> List[str]:
        """Формирует массив аргументов для вызова ssh."""
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
        if self.port != 22:
            cmd.extend(["-p", str(self.port)])
        if self.identity_file:
            cmd.extend(["-i", self.identity_file])

        destination = f"{self.user}@{self.host}" if self.user else self.host
        cmd.append(destination)
        cmd.append(command)
        return cmd

    def run_command(self, command: str, capture_output: bool = False) -> subprocess.CompletedProcess:
        """Выполняет удаленную команду по SSH."""
        if not shutil.which("ssh"):
            raise DeployEngineError("ssh клиент не установлен в локальной системе.")

        cmd = self._build_ssh_cmd(command)
        try:
            return subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as err:
            err_msg = err.stderr if capture_output and err.stderr else str(err)
            raise DeployEngineError(f"Ошибка SSH при выполнении '{command}' на {self.target_host}: {err_msg}")

    def scp_file(self, local_path: str, remote_path: str) -> None:
        """Копирует файл на удаленный хост через scp."""
        if not shutil.which("scp"):
            raise DeployEngineError("scp клиент не установлен в локальной системе.")

        cmd = ["scp", "-o", "StrictHostKeyChecking=accept-new"]
        if self.port != 22:
            cmd.extend(["-P", str(self.port)])
        if self.identity_file:
            cmd.extend(["-i", self.identity_file])

        destination = f"{self.user}@{self.host}:{remote_path}" if self.user else f"{self.host}:{remote_path}"
        cmd.extend([local_path, destination])

        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as err:
            raise DeployEngineError(f"Ошибка scp при передаче {local_path} на {destination}: {err}")
