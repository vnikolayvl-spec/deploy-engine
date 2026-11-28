"""Мост между веб-плагином de-web и Python-ядром Deploy Engine v3.0.0."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

WEB_DIR = Path(__file__).resolve().parent
PKG_ROOT = WEB_DIR.parent
FILES_CANDIDATES = [
    PKG_ROOT / "files",
    Path("/opt/de_deploy-engine/files"),
]
for _cand in FILES_CANDIDATES:
    if _cand.is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))
        break

from lib.core.engine import Engine  # noqa: E402
from lib.core.execution_context import ExecutionContext  # noqa: E402
from lib.core.version_utils import get_engine_version, version_status  # noqa: E402
from lib.state.package_inspector import PackageInspector  # noqa: E402
from lib.ui.plan_executor import PlanExecutor  # noqa: E402

VALID_SANDBOX_OS = {"debian", "ubuntu", "alpine", "arch", "fedora", "macos"}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._/@:-]{1,128}$")


class EngineBridge:
    """Формирует снимок дерева пакетов, предпросмотр плана, детали пакета и синхронизацию репозитория."""

    def __init__(self, search_roots: Optional[List[str]] = None) -> None:
        self.search_roots = search_roots

    @staticmethod
    def validate_id(value: str, label: str = "идентификатор") -> str:
        clean = (value or "").strip()
        if not clean or ".." in clean or not SAFE_ID_RE.match(clean):
            raise ValueError(f"Некорректный {label}: '{value}'")
        return clean

    @staticmethod
    def resolve_sandbox_os(raw_os: Optional[str]) -> str:
        clean = (raw_os or "debian").strip().lower()
        return clean if clean in VALID_SANDBOX_OS else "debian"

    def _detect_search_roots(self) -> Optional[List[str]]:
        if self.search_roots:
            return self.search_roots
        workspace_pkgs = PKG_ROOT.parent / "deploy-packages"
        if workspace_pkgs.is_dir():
            return [str(workspace_pkgs)]
        return None

    def create_engine(
        self,
        sandbox: bool = False,
        sandbox_os: Optional[str] = None,
        dry_run: bool = False,
        purge: bool = False,
        clean_env: bool = False,
        sandbox_dir: Optional[str] = None,
        force_rescan: bool = False,
    ) -> Engine:
        sb_os = self.resolve_sandbox_os(sandbox_os) if sandbox else None
        sb_dir = sandbox_dir or os.path.join(str(PKG_ROOT), ".de_web_sandbox")
        ctx = ExecutionContext(
            dry_run=bool(dry_run),
            purge=bool(purge),
            clean_env=bool(clean_env),
            sandbox=bool(sandbox),
            sandbox_os=sb_os,
            sandbox_dir=sb_dir,
            non_interactive=True,
        )
        engine = Engine(ctx)
        if os.environ.get("DE_PACKAGES_CACHE"):
            engine.registry.cache_manager.cache_file_path = os.environ["DE_PACKAGES_CACHE"]
        if os.environ.get("DE_LOCAL_ENV_DIR"):
            engine.env_manager.local_env_dir = os.environ["DE_LOCAL_ENV_DIR"]
        if os.environ.get("DE_BACKUP_DIR"):
            engine.backup_manager.backup_dir = os.environ["DE_BACKUP_DIR"]
        engine.discover_packages(self._detect_search_roots(), force_rescan=bool(force_rescan or self.search_roots))
        return engine

    def get_state(self, sandbox: bool = False, sandbox_os: Optional[str] = None, active_job_id: Optional[str] = None) -> Dict[str, Any]:
        """Возвращает полный снимок каталога пакетов, категорий, юнитов и доступных бэкапов."""
        eng = self.create_engine(sandbox=sandbox, sandbox_os=sandbox_os)
        inspector = PackageInspector(engine=eng)
        installed_map = eng.state_repo.get_state().get("installed", {}) or {}
        backups_by_pkg: Dict[str, List[Dict[str, Any]]] = {}
        try:
            for b in eng.backup_manager.list_backups():
                p_name = str(b.get("package") or "")
                backups_by_pkg.setdefault(p_name, []).append({
                    "filename": b.get("filename", ""),
                    "timestamp": b.get("timestamp", ""),
                    "size_human": b.get("size_human", ""),
                    "comment": b.get("comment", ""),
                })
        except Exception:
            pass

        packages_out: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()
        for ns, pkg in sorted(eng.packages.items()):
            if pkg.get("is_alias"):
                continue
            pkg_name = pkg.get("name", ns.split("/")[-1])
            seen_keys.add(ns)
            seen_keys.add(pkg_name)
            st = installed_map.get(pkg_name) or installed_map.get(ns)
            inst_v = str(st.get("version")) if st else None
            avail_v = str(pkg.get("version", "1.0.0"))
            units_out = []
            env_spec = PlanExecutor.find_pkg_env_unit(eng, ns)
            for u_name, u_spec in sorted((pkg.get("units") or {}).items()):
                try:
                    _, dest_p, _, u_type = eng.get_paths_and_modes(f"{pkg_name}:{u_name}")
                except Exception:
                    dest_p, u_type = "", str((u_spec or {}).get("type") or "file")
                units_out.append({
                    "name": u_name,
                    "type": u_type,
                    "dest": dest_p,
                    "desc": str((u_spec or {}).get("desc") or ""),
                })
            preset_path = eng.env_manager.get_local_preset_path(pkg_name)
            packages_out.append({
                "key": ns,
                "name": pkg_name,
                "category": pkg.get("folder_path") or "корень",
                "desc": pkg.get("desc") or pkg.get("description") or "",
                "installed": st is not None,
                "installed_version": inst_v,
                "available_version": avail_v,
                "update_status": version_status(inst_v, avail_v) if st else "not_installed",
                "compatible": eng.is_package_compatible(pkg),
                "platforms": list(pkg.get("platforms") or []),
                "requires": list(pkg.get("requires") or []),
                "after": list(pkg.get("after") or []),
                "manifest_available": True,
                "is_external": bool(pkg.get("is_external_manifest")),
                "has_env": env_spec is not None,
                "has_preset": bool(env_spec and os.path.isfile(preset_path)),
                "has_service": any(u["type"] in ("unit", "service", "timer", "plist") for u in units_out),
                "units": units_out,
                "backups": backups_by_pkg.get(pkg_name, []),
            })

        for name, st in sorted(installed_map.items()):
            ns = str((st or {}).get("namespace") or name)
            if ns in seen_keys or name in seen_keys:
                continue
            packages_out.append({
                "key": ns, "name": name, "category": os.path.dirname(ns) or "внешние",
                "desc": str((st or {}).get("desc") or ""), "installed": True,
                "installed_version": str((st or {}).get("version") or "unknown"),
                "available_version": str((st or {}).get("version") or "unknown"),
                "update_status": "current", "compatible": True, "platforms": [],
                "requires": [], "after": [], "manifest_available": False, "is_external": True,
                "has_env": False, "has_preset": False,
                "has_service": bool(inspector.get_package_service_units(name)),
                "units": [], "backups": backups_by_pkg.get(name, []),
            })

        categories = {k: str((v or {}).get("desc") or "") for k, v in (eng.folders or {}).items()}
        roots = self._detect_search_roots() or [eng.provider.get_paths().get("state_dir", "")]
        return {
            "engine_version": get_engine_version(),
            "distro": eng.provider.distro_id,
            "os_family": eng.provider.os_family,
            "sandbox": bool(sandbox),
            "sandbox_os": eng.provider.distro_id,
            "packages_dir": roots[0] if roots else "",
            "local_env_dir": eng.env_manager.local_env_dir,
            "active_job_id": active_job_id,
            "categories": categories,
            "packages": packages_out,
        }

    def preview_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Рассчитывает порядок установки, зависимости, системные пакеты и требования .env для плана."""
        opts = plan.get("options") if isinstance(plan.get("options"), dict) else {}
        eng = self.create_engine(
            sandbox=bool(opts.get("sandbox")),
            sandbox_os=opts.get("sandbox_os"),
            dry_run=bool(opts.get("dry_run")),
        )
        actions = plan.get("actions") if isinstance(plan.get("actions"), dict) else {}
        unit_updates = plan.get("unit_updates") if isinstance(plan.get("unit_updates"), dict) else {}
        backups = list(plan.get("backups") or [])
        restores = plan.get("restores") if isinstance(plan.get("restores"), dict) else {}

        actions_plan: Dict[str, Any] = dict(actions)
        if backups:
            actions_plan["__backup__"] = backups
        if restores:
            actions_plan["__restore__"] = restores
        if unit_updates:
            actions_plan["__unit_updates__"] = unit_updates

        ordered_names, env_specs = PlanExecutor.build_ordered_items(eng, actions_plan)
        explicit_keys = {k for k, v in actions.items() if v in ("install", "reinstall", "uninstall")}
        explicit_names = {eng.registry.get(k)["name"] for k in explicit_keys if eng.registry.has(k)}
        install_targets = [k for k, v in actions.items() if v in ("install", "reinstall") and eng.registry.has(k)]

        skipped_deps: List[str] = []
        warnings: List[str] = []
        if install_targets:
            try:
                _, skipped_deps = eng.dep_graph.resolve_install_order(
                    install_targets, is_installed_fn=eng.state_repo.get_installed_package
                )
            except Exception as err:
                warnings.append(str(err))

        auto_deps = [n for n in ordered_names if n not in explicit_names and n not in backups and n not in restores and n not in unit_updates]
        sys_pkgs: List[str] = []
        for pkg_name in ordered_names:
            if eng.registry.has(pkg_name):
                pkg = eng.registry.get(pkg_name)
                if actions.get(pkg.get("namespace")) in ("install", "reinstall") or pkg_name in auto_deps:
                    for sp in eng.sys_manager.resolve_for_platform(pkg.get("sys_packages", [])):
                        if sp not in sys_pkgs:
                            sys_pkgs.append(sp)

        env_needed: List[Dict[str, Any]] = []
        for pkg_name, (u_name, src_p, dest_p) in env_specs.items():
            needs = eng.env_manager.needs_env_confirmation(pkg_name, src_p)
            env_needed.append({
                "package": pkg_name, "unit": u_name, "needs_confirmation": bool(needs),
                "has_preset": os.path.isfile(eng.env_manager.get_local_preset_path(pkg_name)),
                "dest": dest_p,
            })

        return {
            "ordered_packages": ordered_names,
            "auto_dependencies": auto_deps,
            "skipped_dependencies": skipped_deps,
            "sys_packages": sys_pkgs,
            "env_checks": env_needed,
            "requires_env_wizard": any(e["needs_confirmation"] for e in env_needed),
            "warnings": warnings,
        }

    def get_package_details(self, pkg_key: str, sandbox: bool = False, sandbox_os: Optional[str] = None) -> Optional[Dict[str, Any]]:
        clean = self.validate_id(pkg_key, "пакет")
        eng = self.create_engine(sandbox=sandbox, sandbox_os=sandbox_os)
        return PackageInspector(engine=eng).get_package_info(clean)

    def get_package_logs(self, pkg_key: str, sandbox: bool = False, sandbox_os: Optional[str] = None) -> Dict[str, Any]:
        clean = self.validate_id(pkg_key, "пакет")
        eng = self.create_engine(sandbox=sandbox, sandbox_os=sandbox_os)
        inspector = PackageInspector(engine=eng)
        return {
            "package": clean,
            "install_log": inspector.get_latest_install_log(clean),
            "service_logs": inspector.get_service_logs(clean),
            "has_service": bool(inspector.get_package_service_units(clean)),
        }

    def restart_service(self, pkg_key: str, sandbox: bool = False, sandbox_os: Optional[str] = None) -> Dict[str, Any]:
        clean = self.validate_id(pkg_key, "пакет")
        eng = self.create_engine(sandbox=sandbox, sandbox_os=sandbox_os)
        output = PackageInspector(engine=eng).restart_package_services(clean)
        return {"package": clean, "output": output}

    def sync_packages(self) -> Dict[str, Any]:
        """Выполняет безопасный git pull --ff-only для репозитория пакетов и пересканирование реестра."""
        roots = self._detect_search_roots()
        eng = self.create_engine(force_rescan=False)
        target_dir = Path(roots[0]).resolve() if roots else Path(eng.provider.get_paths().get("state_dir", "/var/lib")) / "de_deploy-engine" / "packages"
        git_output = "Каталог пакетов не является git-репозиторием — выполнено только пересканирование."
        git_updated = False
        if (target_dir / ".git").exists():
            res = subprocess.run(
                ["git", "-C", str(target_dir), "pull", "--ff-only"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            git_output = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
            git_updated = res.returncode == 0
            if res.returncode != 0:
                raise RuntimeError(f"Ошибка git pull: {git_output or 'код ' + str(res.returncode)}")

        count = eng.discover_packages(roots, force_rescan=True)
        return {"packages_dir": str(target_dir), "git_updated": git_updated, "git_output": git_output, "packages_count": count}
