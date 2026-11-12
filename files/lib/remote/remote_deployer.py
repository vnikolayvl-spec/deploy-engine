"""
Remote deployer supporting two-tier execution:
1. Full Mode (/opt/de_deploy-engine or --remote-dir): all CLI commands + Remote TUI.
2. Reduced Mode (no remote deploy-engine): install, uninstall, reinstall, list.
"""
import json
import os
import shlex
import tarfile
import tempfile
from typing import Any, Dict, List, Optional
from lib.config import DEFAULT_REMOTE_ENGINE_DIR, ENGINE_ROOT_DIR, LOCAL_ENV_DIR
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.remote.ssh_client import SSHClient


class RemoteDeployer:
    """Двухуровневый оркестратор удаленного развертывания, инспекции, бэкапов и TUI по SSH."""

    REDUCED_ALLOWED_ACTIONS = {"install", "uninstall", "reinstall", "list"}

    def __init__(self, target_host: str, context: Optional[ExecutionContext] = None, remote_dir: Optional[str] = None, ssh_client: Optional[SSHClient] = None):
        self.context = context or ExecutionContext()
        self.ssh_client = ssh_client or SSHClient(target_host)
        raw_dir = remote_dir or getattr(self.context, "remote_dir", None) or DEFAULT_REMOTE_ENGINE_DIR
        self.remote_dir = raw_dir.rstrip("/")
        self._probed = False
        self._resolved_remote_engine_dir: Optional[str] = None

    def probe_remote_engine(self, force: bool = False) -> Optional[str]:
        """
        Проверяет наличие установленного deploy-engine на удаленном сервере
        (в <remote_dir>/deploy.py или <remote_dir>/files/deploy.py).
        Возвращает путь к рабочей директории движка на сервере или None (сокращенный режим).
        """
        if self._probed and not force:
            return self._resolved_remote_engine_dir

        c1 = f"{self.remote_dir}/deploy.py"
        c2 = f"{self.remote_dir}/files/deploy.py"
        q_dir = shlex.quote(self.remote_dir)
        q_files = shlex.quote(f"{self.remote_dir}/files")
        probe_cmd = (
            f"if [ -f {shlex.quote(c1)} ]; then echo {q_dir}; "
            f"elif [ -f {shlex.quote(c2)} ]; then echo {q_files}; "
            f"else echo '__MISSING__'; fi"
        )
        try:
            res = self.ssh_client.run_command(probe_cmd, capture_output=True)
            out = (res.stdout or "").strip().splitlines()
            first = out[-1].strip() if out else "__MISSING__"
            self._resolved_remote_engine_dir = None if (not first or first == "__MISSING__") else first
        except Exception:
            self._resolved_remote_engine_dir = None

        self._probed = True
        return self._resolved_remote_engine_dir

    def is_full_mode(self) -> bool:
        """Возвращает True, если на удаленном сервере обнаружен установленный deploy-engine."""
        return self.probe_remote_engine() is not None

    def ensure_action_supported(self, action: str) -> Optional[str]:
        """Проверяет, поддерживается ли запрошенная команда в текущем режиме удаленного сервера."""
        engine_dir = self.probe_remote_engine()
        if engine_dir:
            return engine_dir
        if action not in self.REDUCED_ALLOWED_ACTIONS:
            raise DeployEngineError(
                f"На удаленном сервере '{self.ssh_client.target_host}' не обнаружен deploy-engine в '{self.remote_dir}'. "
                f"В сокращенном режиме доступны только команды: install, uninstall, reinstall, list. "
                f"Команда '{action}' требует полного режима — установите deploy-engine в /opt/de_deploy-engine "
                f"(или укажите кастомный путь через --remote-dir)."
            )
        return None

    def fetch_remote_state(self) -> Dict[str, Any]:
        """Считывает состояние установленных пакетов с удаленного хоста."""
        engine_dir = self.probe_remote_engine()
        if engine_dir:
            cmd = f"cd {shlex.quote(engine_dir)} && sudo python3 deploy.py list --json 2>/dev/null || cat /etc/default/state.json 2>/dev/null || echo '{{\"installed\":{{}}}}'"
        else:
            cmd = "cat /etc/default/state.json 2>/dev/null || echo '{\"installed\":{}}'"
        try:
            res = self.ssh_client.run_command(cmd, capture_output=True)
            parsed = json.loads((res.stdout or "").strip() or "{}")
            if isinstance(parsed, dict) and ("installed" in parsed or "installed_packages" in parsed):
                inst = parsed.get("installed") or parsed.get("installed_packages") or {}
                return {"installed": inst, "installed_packages": inst}
            if isinstance(parsed, dict):
                return {"installed": parsed, "installed_packages": parsed}
            return {"installed": {}, "installed_packages": {}}
        except Exception as err:
            raise DeployEngineError(f"Не удалось получить состояние с удаленного хоста: {err}")

    def fetch_remote_os_info(self) -> Dict[str, str]:
        """Определяет семейство ОС и дистрибутив удаленного сервера для фильтрации пакетов в Remote TUI."""
        cmd = "uname -s 2>/dev/null; ( . /etc/os-release 2>/dev/null && echo \"$ID\" ) || echo linux"
        try:
            res = self.ssh_client.run_command(cmd, capture_output=True)
            lines = [ln.strip().lower() for ln in (res.stdout or "").splitlines() if ln.strip()]
            uname_s = lines[0] if lines else "linux"
            distro_id = lines[1] if len(lines) > 1 else ("macos" if "darwin" in uname_s else "debian")
            os_family = "macos" if "darwin" in uname_s else "linux"
            return {"os_family": os_family, "distro_id": "macos" if os_family == "macos" else distro_id}
        except Exception:
            return {"os_family": "linux", "distro_id": "debian"}

    def _build_cli_flags(self) -> str:
        """Формирует строку флагов CLI из ExecutionContext для удаленного вызова deploy.py."""
        flags: List[str] = []
        if self.context.dry_run:
            flags.append("--dry-run")
        if self.context.purge:
            flags.append("--purge")
        if self.context.clean_env:
            flags.append("--clean-env")
        if self.context.rescan:
            flags.append("--rescan")
        if self.context.json_output:
            flags.append("--json")
        if self.context.verbose:
            flags.append("--verbose")
        if getattr(self.context, "list_backups", False):
            flags.append("--list")
        if getattr(self.context, "comment", ""):
            flags.append(f"--comment {shlex.quote(self.context.comment)}")
        if getattr(self.context, "backup_selector", None):
            flags.append(f"--backup {shlex.quote(str(self.context.backup_selector))}")
        return " ".join(flags)

    def _sync_packages_and_env_to_remote(self, remote_engine_dir: str, targets: List[str], engine=None) -> None:
        """Передает выбранные папки пакетов и локальные пресеты deploy-engine/env/<pkg>.env в серверный deploy-engine."""
        pkg_dirs: Dict[str, str] = {}
        env_files: Dict[str, str] = {}
        if engine and getattr(engine, "registry", None):
            to_collect = list(targets)
            try:
                valid = [t for t in targets if engine.registry.has(t)]
                if valid:
                    to_collect = engine.dep_graph.resolve_order(valid)
            except Exception:
                pass
            for t in to_collect:
                if engine.registry.has(t):
                    p_info = engine.registry.get(t)
                    pname = p_info.get("name", t.split("/")[-1])
                    bdir = p_info.get("base_dir", "")
                    if bdir and os.path.isdir(bdir):
                        rel_folder = p_info.get("folder_path", "")
                        rel_dest = os.path.join(rel_folder, pname) if rel_folder else pname
                        pkg_dirs[rel_dest] = os.path.abspath(bdir)
                    preset = os.path.join(LOCAL_ENV_DIR, f"{pname}.env")
                    if os.path.isfile(preset):
                        env_files[f"{pname}.env"] = preset

        if os.path.isdir(LOCAL_ENV_DIR):
            for fname in os.listdir(LOCAL_ENV_DIR):
                if fname.endswith(".env") and fname not in env_files:
                    env_files[fname] = os.path.join(LOCAL_ENV_DIR, fname)

        if not pkg_dirs and not env_files:
            return

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            sync_archive = tmp.name
        try:
            with tarfile.open(sync_archive, "w:gz") as tar:
                for rel_pkg, abs_dir in pkg_dirs.items():
                    tar.add(abs_dir, arcname=os.path.join("packages", rel_pkg))
                for env_name, abs_env in env_files.items():
                    tar.add(abs_env, arcname=os.path.join("env", env_name))
            remote_tmp = "/tmp/de_sync_payload.tar.gz"
            self.ssh_client.scp_file(sync_archive, remote_tmp)
            target_data_root = "/var/lib/de_deploy-engine" if remote_engine_dir.startswith("/opt/de_deploy-engine") else remote_engine_dir
            q_data = shlex.quote(target_data_root)
            cmd = f"sudo mkdir -p {q_data}/packages {q_data}/env && sudo tar -xzf {remote_tmp} -C {q_data} && sudo chmod 700 {q_data}/env 2>/dev/null || true && rm -f {remote_tmp}"
            self.ssh_client.run_command(cmd, capture_output=False)
        finally:
            if os.path.exists(sync_archive):
                try:
                    os.remove(sync_archive)
                except OSError:
                    pass

    def execute_remote(self, targets: List[str], action: str = "install", engine=None) -> None:
        """Выполняет операцию на удаленном сервере в Полном или Сокращенном режиме."""
        remote_engine_dir = self.ensure_action_supported(action)
        if remote_engine_dir:
            self._execute_full_mode(remote_engine_dir, targets, action, engine=engine)
        else:
            self._execute_reduced_mode(targets, action, engine=engine)

    def _execute_full_mode(self, remote_engine_dir: str, targets: List[str], action: str, engine=None) -> None:
        """Полный режим: использует установленный deploy-engine в /opt/de_deploy-engine (или --remote-dir)."""
        self.context.log(f"🌐 [ПОЛНЫЙ РЕЖИМ] Сервер {self.ssh_client.target_host} (движок: {remote_engine_dir})")
        if action in ("install", "reinstall", "info", "scan") and not getattr(self.context, "list_backups", False):
            self._sync_packages_and_env_to_remote(remote_engine_dir, targets, engine=engine)

        flags_str = self._build_cli_flags()
        targets_str = " ".join(shlex.quote(t) for t in targets)
        rescan_flag = "--rescan" if action in ("install", "reinstall", "info") else ""
        q_eng = shlex.quote(remote_engine_dir)
        remote_cmd = f"cd {q_eng} && sudo python3 deploy.py {action} {targets_str} {rescan_flag} {flags_str}".strip()
        self.ssh_client.run_command(remote_cmd, capture_output=False)

    def _execute_reduced_mode(self, targets: List[str], action: str, engine=None) -> None:
        """Сокращенный режим: временный бандл в /tmp/de_deploy_run (только install, uninstall, reinstall, list)."""
        self.context.log(
            f"⚡ [СОКРАЩЕННЫЙ РЕЖИМ] На {self.ssh_client.target_host} нет '{self.remote_dir}'. Используется временный бандл..."
        )
        if action == "list":
            state = self.fetch_remote_state()
            installed = state.get("installed", {})
            if self.context.json_output:
                print(json.dumps(installed, indent=2, ensure_ascii=False))
            elif not installed:
                print(f"На удаленном хосте {self.ssh_client.target_host} нет установленных пакетов.")
            else:
                print(f"📦 Установленные пакеты на {self.ssh_client.target_host} (сокращенный режим):")
                for k, v in installed.items():
                    print(f"  • {k} (версия {v.get('version', 'N/A')})")
            return

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp_bundle:
            bundle_path = tmp_bundle.name
        try:
            with tarfile.open(bundle_path, "w:gz") as tar:
                def exclude_filter(tarinfo):
                    for ig in (".git", ".venv", "node_modules", "__pycache__", "dist", "backup"):
                        if ig in tarinfo.name.split("/"):
                            return None
                    return tarinfo
                tar.add(ENGINE_ROOT_DIR, arcname="deploy_engine", filter=exclude_filter)
                if engine and getattr(engine, "registry", None):
                    for p_info in engine.registry.packages.values():
                        if p_info.get("is_alias"):
                            continue
                        bdir = p_info.get("base_dir", "")
                        pname = p_info.get("name", "")
                        if bdir and os.path.isdir(bdir) and pname:
                            rel_f = p_info.get("folder_path", "")
                            arc = os.path.join("deploy_engine", "packages", rel_f, pname) if rel_f else os.path.join("deploy_engine", "packages", pname)
                            tar.add(os.path.abspath(bdir), arcname=arc, filter=exclude_filter)

            remote_archive, remote_dir = "/tmp/de_bundle.tar.gz", "/tmp/de_deploy_run"
            self.ssh_client.scp_file(bundle_path, remote_archive)
            flags_str = self._build_cli_flags()
            targets_str = " ".join(shlex.quote(t) for t in targets)
            remote_cmd = (
                f"rm -rf {remote_dir} && mkdir -p {remote_dir} && "
                f"tar -xzf {remote_archive} -C {remote_dir} && "
                f"cd {remote_dir}/deploy_engine && "
                f"sudo python3 deploy.py {action} {targets_str} --rescan {flags_str}; "
                f"RET=$?; rm -rf {remote_dir} {remote_archive}; exit $RET"
            )
            self.ssh_client.run_command(remote_cmd, capture_output=False)
        finally:
            if os.path.exists(bundle_path):
                try:
                    os.remove(bundle_path)
                except OSError:
                    pass

    def prepare_remote_tui(self, engine) -> str:
        """
        Вариант 2 (Клиент-серверный Remote TUI):
        Проверяет наличие deploy-engine на сервере, загружает его state.json и ОС в локальный Engine.
        """
        remote_engine_dir = self.ensure_action_supported("tui")
        assert remote_engine_dir is not None
        remote_state = self.fetch_remote_state()
        os_info = self.fetch_remote_os_info()

        engine.provider.os_family = os_info["os_family"]
        engine.provider.distro_id = os_info["distro_id"]

        tmp_state = tempfile.NamedTemporaryFile(prefix="de_remote_state_", suffix=".json", delete=False)
        with open(tmp_state.name, "w", encoding="utf-8") as f:
            json.dump(remote_state, f, indent=2, ensure_ascii=False)
        engine.state_repo._explicit_state_file = tmp_state.name
        engine.state_repo.state_file_path = tmp_state.name
        return remote_engine_dir

    def execute_tui_plan(self, actions_plan: Dict[str, str], engine) -> None:
        """Выполняет сформированный в локальном TUI план на удаленном сервере через серверный deploy-engine."""
        to_uninstall = [k for k, v in actions_plan.items() if v == "uninstall" and engine.registry.has(k)]
        to_reinstall = [k for k, v in actions_plan.items() if v == "reinstall" and engine.registry.has(k)]
        to_install = [k for k, v in actions_plan.items() if v == "install" and engine.registry.has(k)]
        for pkg in to_uninstall:
            self.execute_remote([pkg], action="uninstall", engine=engine)
        for pkg in to_reinstall:
            self.execute_remote([pkg], action="reinstall", engine=engine)
        if to_install:
            self.execute_remote(to_install, action="install", engine=engine)
