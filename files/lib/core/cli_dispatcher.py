"""
Диспетчер CLI-команд Deploy Engine v3.0.0:
обрабатывает --version, upgrade, config --show, точечные юниты <pkg>:<unit> / --only / --unit-type
и стандартные операции (install, uninstall, reinstall, backup, restore, list, info, scan, completion, help).
"""
import argparse
import json
import os
from typing import List, Optional, Tuple

from lib.core.completion_provider import CompletionProvider
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.core.version_utils import get_engine_version
from lib.env.env_config_editor import EnvConfigEditor
from lib.env.env_inspector import EnvInspector
from lib.installer.selective_unit_runner import SelectiveUnitRunner
from lib.remote.remote_deployer import RemoteDeployer
from lib.state.package_inspector import PackageInspector
from lib.utils import check_root


def extract_restore_selector(
    engine: Engine, targets: List[str], explicit_selector: Optional[str]
) -> Tuple[List[str], Optional[str]]:
    """Если вызвано 'restore <pkg> <index_or_ts>', отделяет селектор бэкапа от имени пакета."""
    if explicit_selector or len(targets) != 2:
        return targets, explicit_selector
    first, second = targets[0], targets[1]
    if first.lower() != "all" and (
        second.isdigit()
        or second.endswith(".tar.gz")
        or (not engine.registry.has(second) and (engine.context.remote or engine.backup_manager.list_package_backups(first)))
    ):
        return [first], second
    return targets, explicit_selector


def load_engine_sources(
    engine: Engine, args: argparse.Namespace, action: str, targets: List[str]
) -> Tuple[List[str], Optional[int]]:
    """Загружает манифесты пакетов из --manifest, --packages-dir или стандартных путей."""
    if args.manifest and os.path.isdir(args.manifest):
        args.packages_dir, args.manifest = args.manifest, None

    if args.manifest:
        if not os.path.isfile(args.manifest):
            raise DeployEngineError(f"Источник манифеста '{args.manifest}' не найден.")
        engine.load_manifest_recursive(args.manifest)
        if not targets and action in ("install", "uninstall", "reinstall", "upgrade", "backup", "restore", "info", "config"):
            targets = engine.infer_targets_from_manifest(args.manifest)
        return targets, None

    if args.packages_dir:
        if not os.path.isdir(args.packages_dir):
            raise DeployEngineError(f"Директория пакетов '{args.packages_dir}' не найдена.")
        return targets, engine.discover_packages(search_roots=[args.packages_dir], force_rescan=True)

    return targets, engine.discover_packages(force_rescan=(action in ("scan", "tui") or args.rescan))


def _dispatch_config(engine: Engine, targets: List[str], args: argparse.Namespace) -> None:
    if not targets:
        raise DeployEngineError(
            "Укажите имя пакета (например: deploy-engine config <пакет> [--preset] [--show] [--reveal])."
        )
    if getattr(args, "show_config", False):
        inspector = EnvInspector(engine)
        reports = []
        for target in targets:
            rep = inspector.inspect(target, reveal=bool(getattr(args, "reveal", False)), preset=bool(args.preset))
            if rep is None:
                engine.context.log(engine.target_validator.format_missing_warning(target))
            else:
                reports.append(rep)
        if not reports:
            return
        if args.json_output:
            payload = reports[0] if len(reports) == 1 else reports
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("\n\n".join(inspector.format_table(r) for r in reports))
        return

    editor = EnvConfigEditor(engine)
    for target in targets:
        editor.open_config(target, preset=bool(args.preset))


def _dispatch_install_or_reinstall(
    engine: Engine, action: str, targets: List[str], args: argparse.Namespace
) -> None:
    only_units = getattr(args, "only_units", None)
    unit_type = getattr(args, "unit_type", None)
    with_hooks = bool(getattr(args, "with_hooks", False))
    full_pkgs, unit_map = SelectiveUnitRunner.split_targets_and_units(
        targets, only_units=only_units, unit_type=unit_type
    )
    for pkg_q, u_names in unit_map.items():
        engine.update_units(pkg_q, unit_names=u_names or None, unit_type=unit_type, with_hooks=with_hooks)
    if full_pkgs:
        if action == "install":
            engine.install_packages(full_pkgs)
        else:
            for target in full_pkgs:
                engine.reinstall_package(target)


def dispatch_cli(
    action: str,
    targets: List[str],
    args: argparse.Namespace,
    context: ExecutionContext,
    parser: argparse.ArgumentParser,
) -> None:
    """Выполняет CLI-команду Deploy Engine."""
    if getattr(args, "show_version", False) or action == "version":
        ver = get_engine_version()
        if args.json_output:
            print(json.dumps({"name": "deploy-engine", "version": ver}, indent=2, ensure_ascii=False))
        else:
            print(f"Deploy Engine v{ver}")
        return

    if action == "help":
        parser.print_help()
        return

    engine = Engine(context)
    targets, scanned_count = load_engine_sources(engine, args, action, targets)

    if action == "completion":
        mode = targets[0] if targets else "packages"
        out = CompletionProvider(engine).render(mode)
        if out:
            print(out)
        return

    if action == "scan" and not args.remote:
        src_note = f" из '{args.packages_dir}'" if args.packages_dir else ""
        print(f"✅ База пакетов успешно обновлена{src_note}. Обнаружено пакетов: {scanned_count or 0} (сохранено в packages.json).")
        return

    if args.remote:
        deployer = RemoteDeployer(args.remote, context, remote_dir=args.remote_dir)
        if action == "restore" and not args.list_backups:
            targets, context.backup_selector = extract_restore_selector(engine, targets, args.backup_selector)
        if action not in ("list", "scan", "upgrade") and not args.list_backups and not targets:
            raise DeployEngineError(f"Укажите имена пакетов (или 'all') для удаленной операции '{action}'.")
        deployer.execute_remote(targets, action, engine=engine)
        return

    if action == "list":
        inspector = PackageInspector(state_repo=engine.state_repo, engine=engine)
        print(inspector.to_json() if args.json_output else inspector.format_table())
        return

    if action == "info":
        if not targets:
            raise DeployEngineError("Укажите имя пакета для просмотра информации (например: deploy-engine info <пакет>).")
        inspector = PackageInspector(state_repo=engine.state_repo, engine=engine)
        print(inspector.info_to_json(targets) if args.json_output else "\n\n".join(inspector.format_package_info(t) for t in targets))
        return

    if action == "config":
        _dispatch_config(engine, targets, args)
        return

    if action in ("backup", "restore") and args.list_backups:
        if args.json_output:
            pkgs = engine.backup_manager.resolve_targets(targets or ["all"], for_restore=True)
            print(json.dumps({p: engine.backup_manager.list_package_backups(p) for p in pkgs}, indent=2, ensure_ascii=False))
        else:
            print(engine.backup_manager.format_backups_list(targets or ["all"]))
        return

    if action == "upgrade":
        if not args.dry_run and engine.provider.requires_root():
            check_root()
        res = engine.upgrade_packages(targets or ["all"])
        if args.json_output:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    if not targets:
        raise DeployEngineError(f"Не указано имя пакета (или 'all') для операции '{action}'.")
    if not args.dry_run and action != "backup" and engine.provider.requires_root():
        check_root()

    if action in ("install", "reinstall"):
        _dispatch_install_or_reinstall(engine, action, targets, args)
    elif action == "uninstall":
        for target in targets:
            engine.uninstall_package(target)
    elif action == "backup":
        res = engine.backup_packages(targets, comment=args.comment)
        if args.json_output:
            print(json.dumps(res, indent=2, ensure_ascii=False))
    elif action == "restore":
        r_targets, selector = extract_restore_selector(engine, targets, args.backup_selector)
        res = engine.restore_packages(r_targets, selector=selector)
        if args.json_output:
            print(json.dumps(res, indent=2, ensure_ascii=False))
