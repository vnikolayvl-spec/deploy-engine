"""
lib/ui/plan_executor.py: Планирование порядка вкладок и синхронное выполнение плана операций TUI.
"""
import os
from typing import Any, Dict, List, Optional, Tuple


class PlanExecutor:
    """Формирует упорядоченный список пакетов плана TUI и выполняет операции в строгом порядке."""

    @staticmethod
    def find_pkg_env_unit(engine, pkg_key: str) -> Optional[Tuple[str, str, str]]:
        """Возвращает (unit_name, src_path, dest_path) для .env юнита пакета или None."""
        if not engine.registry.has(pkg_key):
            return None
        pkg = engine.registry.get(pkg_key)
        pkg_name = pkg.get("name", pkg_key.split("/")[-1])
        for u_name, u_spec in sorted((pkg.get("units") or {}).items()):
            if (u_spec or {}).get("type") == "env" or u_name.endswith(".env") or u_name == "deploy.env":
                try:
                    src_path, dest_path, _, _ = engine.get_paths_and_modes(f"{pkg_name}:{u_name}")
                    if os.path.isfile(src_path):
                        return u_name, src_path, dest_path
                except Exception:
                    continue
        return None

    @classmethod
    def build_ordered_items(cls, engine, actions_plan: Dict[str, Any]) -> Tuple[List[str], Dict[str, Tuple[str, str, str]]]:
        """Возвращает (ordered_pkg_names, pkg_env_specs) с учетом зависимостей (пропуская установленные)."""
        raw_order: List[Tuple[str, bool]] = []
        for b_pkg in actions_plan.get("__backup__") or []:
            if engine.registry.has(b_pkg):
                raw_order.append((b_pkg, False))
        for r_pkg in (actions_plan.get("__restore__") or {}).keys():
            if engine.registry.has(r_pkg):
                raw_order.append((r_pkg, False))
        for k, v in actions_plan.items():
            if v == "uninstall" and engine.registry.has(k):
                raw_order.append((k, False))
        for mode in ("reinstall", "install"):
            targets = [k for k, v in actions_plan.items() if v == mode and engine.registry.has(k)]
            if targets:
                try:
                    resolved, _ = engine.dep_graph.resolve_install_order(
                        targets, is_installed_fn=engine.state_repo.get_installed_package
                    )
                except Exception:
                    resolved = targets
                for r_key in resolved:
                    if engine.registry.has(r_key):
                        raw_order.append((r_key, True))

        ordered_names: List[str] = []
        env_specs: Dict[str, Tuple[str, str, str]] = {}
        for pkg_key, needs_env in raw_order:
            pkg = engine.registry.get(pkg_key)
            pkg_name = pkg.get("name", pkg_key.split("/")[-1])
            if pkg_name not in ordered_names:
                ordered_names.append(pkg_name)
            if needs_env and pkg_name not in env_specs:
                env_spec = cls.find_pkg_env_unit(engine, pkg_key)
                if env_spec:
                    env_specs[pkg_name] = env_spec
        return ordered_names, env_specs

    @staticmethod
    def execute_plan(engine, actions_plan: Dict[str, Any], remote_deployer=None) -> None:
        """Выполняет шаги плана в строгом порядке: backup -> restore -> uninstall -> reinstall -> install."""
        if remote_deployer:
            remote_deployer.execute_tui_plan(actions_plan, engine)
            return
        to_backup = [p for p in (actions_plan.get("__backup__") or []) if engine.registry.has(p)]
        to_restore = {p: s for p, s in (actions_plan.get("__restore__") or {}).items() if s and engine.registry.has(p)}
        to_uninstall = [k for k, v in actions_plan.items() if v == "uninstall" and engine.registry.has(k)]
        to_reinstall = [k for k, v in actions_plan.items() if v == "reinstall" and engine.registry.has(k)]
        to_install = [k for k, v in actions_plan.items() if v == "install" and engine.registry.has(k)]
        if to_backup:
            engine.backup_packages(to_backup, comment=getattr(engine.context, "comment", ""))
        for pkg, arch_selector in to_restore.items():
            engine.restore_packages([pkg], selector=arch_selector)
        for pkg in to_uninstall:
            engine.uninstall_package(pkg)
        for pkg in to_reinstall:
            engine.reinstall_package(pkg)
        if to_install:
            engine.install_packages(to_install)
