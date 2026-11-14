#!/usr/bin/env python3
"""
main.py: Единая точка входа Deploy Engine (CLI + TUI).
- При запуске с CLI-командой (install, uninstall, reinstall, backup, restore, list, info, scan, help) работает как CLI.
- При запуске без CLI-команды или с флагом --tui (-u) открывает интерактивный TUI-интерфейс.
- Обеспечивает сквозной перехват KeyboardInterrupt (Ctrl+C) с кодом выхода 130 без стектрейса.
"""
import argparse
import json
import os
import sys
from typing import List, Optional, Tuple

from lib.config import DEFAULT_REMOTE_ENGINE_DIR
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.remote.remote_deployer import RemoteDeployer
from lib.state.package_inspector import PackageInspector
from lib.utils import bootstrap_gui, check_root

VALID_ACTIONS = {"install", "uninstall", "reinstall", "backup", "restore", "list", "info", "scan", "tui", "help"}


def build_parser() -> argparse.ArgumentParser:
    """Создает единый парсер аргументов командной строки для CLI и TUI."""
    parser = argparse.ArgumentParser(
        prog="deploy-engine",
        description=(
            "Deploy Engine: Модульный кроссплатформенный оркестратор пакетов.\n"
            "• Запуск без команды (или с флагом --tui) открывает интерактивный TUI-интерфейс.\n"
            "• Запуск с командой (install, uninstall, reinstall, backup, restore, list, info, scan) работает в CLI-режиме."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("pos_args", nargs="*", help="Команда (install|uninstall|reinstall|backup|restore|list|info|scan|tui) и/или цели/путь к пакетам")
    parser.add_argument("--tui", "-u", dest="force_tui", action="store_true", help="Принудительно открыть интерактивный TUI-интерфейс")
    parser.add_argument("--info", "-i", dest="info_flag", nargs="?", const="__FLAG_ONLY__", default=None, help="Показать описание пакета, статус и пути установки")
    parser.add_argument("--comment", "-c", dest="comment", default="", help="Комментарий к создаваемому бэкапу (для команды backup)")
    parser.add_argument("--backup", "-b", dest="backup_selector", default=None, help="Номер (1, 2...), метка времени или имя архива для restore")
    parser.add_argument("--list", "-l", dest="list_backups", action="store_true", help="Показать список доступных бэкапов (для backup и restore)")
    parser.add_argument("--manifest", "-m", dest="manifest", default=None, help="Путь к manifest.json пакета или к корневой папке дерева пакетов")
    parser.add_argument("--packages-dir", "-d", dest="packages_dir", default=None, help="Путь к папке-источнику дерева пакетов")
    parser.add_argument("--sandbox", dest="sandbox_os", nargs="?", const="auto", default=None, help="Тестовый режим песочницы (debian, ubuntu, alpine, arch, macos)")
    parser.add_argument("--sandbox-dir", dest="sandbox_dir", default=None, help="Путь к директории локальной песочницы (по умолчанию ./.de_sandbox)")
    parser.add_argument("--dry-run", "-n", dest="dry_run", action="store_true", help="Симуляция без модификации системы")
    parser.add_argument("--purge", dest="purge", action="store_true", help="Полное удаление каталогов ENV и Data при удалении")
    parser.add_argument("--clean-env", dest="clean_env", action="store_true", help="Сброс переменных окружения к заводским настройкам")
    parser.add_argument("--rescan", dest="rescan", action="store_true", help="Принудительный переобход директорий и обновление packages.json")
    parser.add_argument("--remote", "-r", dest="remote", default=None, help="Удаленный хост [user@]host[:port]")
    parser.add_argument("--remote-dir", dest="remote_dir", default=DEFAULT_REMOTE_ENGINE_DIR, help=f"Путь к deploy-engine на удаленном сервере (по умолчанию {DEFAULT_REMOTE_ENGINE_DIR})")
    parser.add_argument("--config", dest="config_file", default=None, help="Путь к кастомному env-файлу конфигурации движка")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Вывод информации в формате JSON")
    parser.add_argument("--verbose", "-v", dest="verbose", action="store_true", help="Подробный отладочный вывод")
    return parser


def resolve_mode_and_targets(args: argparse.Namespace) -> Tuple[str, List[str]]:
    """
    Определяет режим работы ('tui' или имя CLI-действия), источник манифестов и список целевых пакетов.
    Поддерживает позиционное указание пути к манифесту/папке как до, так и после команды.
    """
    tokens = list(args.pos_args or [])
    if args.info_flag is not None:
        if args.info_flag != "__FLAG_ONLY__" and args.info_flag not in tokens:
            tokens.insert(0, args.info_flag)
        return "info", [t for t in tokens if t != "info"]

    if args.force_tui:
        tokens = [t for t in tokens if t != "tui"]
        if tokens and not args.manifest and not args.packages_dir:
            first = tokens[0]
            if os.path.isdir(first):
                args.packages_dir = first
            elif os.path.isfile(first):
                args.manifest = first
        return "tui", []

    action: Optional[str] = None
    remaining: List[str] = []
    for tok in tokens:
        if action is None and tok in VALID_ACTIONS:
            action = tok
        else:
            remaining.append(tok)

    if action is None or action == "tui":
        if remaining and not args.manifest and not args.packages_dir:
            first = remaining[0]
            if os.path.isdir(first):
                args.packages_dir = first
                remaining = remaining[1:]
            elif os.path.isfile(first):
                args.manifest = first
                remaining = remaining[1:]
        return "tui", ([] if action == "tui" else remaining)

    if remaining and not args.manifest and not args.packages_dir:
        first = remaining[0]
        if first.endswith(".json") and os.path.isfile(first):
            args.manifest = first
            remaining = remaining[1:]
        elif os.path.isdir(first) and (action == "scan" or len(remaining) > 1):
            args.packages_dir = first
            remaining = remaining[1:]

    return action, remaining


def _extract_restore_selector(engine: Engine, targets: List[str], explicit_selector: Optional[str]) -> Tuple[List[str], Optional[str]]:
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


def _load_engine_sources(engine: Engine, args: argparse.Namespace, action: str, targets: List[str]) -> Tuple[List[str], Optional[int]]:
    """Загружает манифесты пакетов из --manifest, --packages-dir или стандартных путей."""
    if args.manifest and os.path.isdir(args.manifest):
        args.packages_dir, args.manifest = args.manifest, None

    if args.manifest:
        if not os.path.isfile(args.manifest):
            raise DeployEngineError(f"Источник манифеста '{args.manifest}' не найден.")
        engine.load_manifest_recursive(args.manifest)
        if not targets and action in ("install", "uninstall", "reinstall", "backup", "restore", "info"):
            targets = engine.infer_targets_from_manifest(args.manifest)
        return targets, None

    if args.packages_dir:
        if not os.path.isdir(args.packages_dir):
            raise DeployEngineError(f"Директория пакетов '{args.packages_dir}' не найдена.")
        return targets, engine.discover_packages(search_roots=[args.packages_dir], force_rescan=True)

    return targets, engine.discover_packages(force_rescan=(action in ("scan", "tui") or args.rescan))


def run_tui(args: argparse.Namespace, context: ExecutionContext) -> None:
    """Запускает интерактивный TUI-интерфейс (локально, в песочнице или в режиме Remote TUI)."""
    bootstrap_gui()
    from lib.ui_app import DeployApp

    engine = Engine(context)
    _load_engine_sources(engine, args, "tui", [])

    remote_deployer = None
    if args.remote:
        remote_deployer = RemoteDeployer(args.remote, context, remote_dir=args.remote_dir)
        context.remote_dir = remote_deployer.prepare_remote_tui(engine)

    if not engine.packages and not getattr(engine, "folders", {}):
        print(
            "Использование TUI: deploy-engine [путь_к_папке | путь_к_manifest.json] "
            "[--remote [user@]host[:port]] [--remote-dir /opt/de_deploy-engine] [--sandbox [debian|macos]]"
        )
        return

    app = DeployApp(engine, remote_deployer=remote_deployer)
    actions_plan = app.run()

    if actions_plan and isinstance(actions_plan, dict):
        if remote_deployer:
            remote_deployer.execute_tui_plan(actions_plan, engine)
        else:
            to_backup = [p for p in (actions_plan.get("__backup__") or []) if engine.registry.has(p)]
            to_restore = {p: s for p, s in (actions_plan.get("__restore__") or {}).items() if s and engine.registry.has(p)}
            to_uninstall = [k for k, v in actions_plan.items() if v == "uninstall" and engine.registry.has(k)]
            to_reinstall = [k for k, v in actions_plan.items() if v == "reinstall" and engine.registry.has(k)]
            to_install = [k for k, v in actions_plan.items() if v == "install" and engine.registry.has(k)]

            if to_backup:
                engine.backup_packages(to_backup, comment=args.comment)
            for pkg, arch_selector in to_restore.items():
                engine.restore_packages([pkg], selector=arch_selector)
            for pkg in to_uninstall:
                engine.uninstall_package(pkg)
            for pkg in to_reinstall:
                print(f"\n🔄 TUI: Запуск переустановки пакета: {pkg.upper()}")
                engine.reinstall_package(pkg)
            if to_install:
                engine.install_packages(to_install)


def run_cli(action: str, targets: List[str], args: argparse.Namespace, context: ExecutionContext, parser: argparse.ArgumentParser) -> None:
    """Выполняет CLI-команду (install, uninstall, reinstall, backup, restore, list, info, scan, help)."""
    if action == "help":
        parser.print_help()
        return

    engine = Engine(context)
    targets, scanned_count = _load_engine_sources(engine, args, action, targets)

    if action == "scan" and not args.remote:
        src_note = f" из '{args.packages_dir}'" if args.packages_dir else ""
        print(f"✅ База пакетов успешно обновлена{src_note}. Обнаружено пакетов: {scanned_count or 0} (сохранено в packages.json).")
        return

    if args.remote:
        deployer = RemoteDeployer(args.remote, context, remote_dir=args.remote_dir)
        if action == "restore" and not args.list_backups:
            targets, context.backup_selector = _extract_restore_selector(engine, targets, args.backup_selector)
        if action not in ("list", "scan") and not args.list_backups and not targets:
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

    if action in ("backup", "restore") and args.list_backups:
        if args.json_output:
            pkgs = engine.backup_manager.resolve_targets(targets or ["all"], for_restore=True)
            print(json.dumps({p: engine.backup_manager.list_package_backups(p) for p in pkgs}, indent=2, ensure_ascii=False))
        else:
            print(engine.backup_manager.format_backups_list(targets or ["all"]))
        return

    if not targets:
        raise DeployEngineError(f"Не указано имя пакета (или 'all') для операции '{action}'.")

    if not args.dry_run and action != "backup" and engine.provider.requires_root():
        check_root()

    if action == "install":
        engine.install_packages(targets)
    elif action == "uninstall":
        for target in targets:
            engine.uninstall_package(target)
    elif action == "reinstall":
        for target in targets:
            engine.reinstall_package(target)
    elif action == "backup":
        res = engine.backup_packages(targets, comment=args.comment)
        if args.json_output:
            print(json.dumps(res, indent=2, ensure_ascii=False))
    elif action == "restore":
        r_targets, selector = _extract_restore_selector(engine, targets, args.backup_selector)
        res = engine.restore_packages(r_targets, selector=selector)
        if args.json_output:
            print(json.dumps(res, indent=2, ensure_ascii=False))


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    action, targets = resolve_mode_and_targets(args)

    context = ExecutionContext(
        dry_run=args.dry_run,
        purge=args.purge,
        clean_env=args.clean_env,
        verbose=args.verbose,
        remote=args.remote,
        remote_dir=args.remote_dir,
        rescan=args.rescan,
        json_output=args.json_output,
        sandbox=bool(args.sandbox_os is not None or args.sandbox_dir is not None),
        sandbox_os=args.sandbox_os,
        sandbox_dir=args.sandbox_dir,
        comment=args.comment,
        backup_selector=args.backup_selector,
        list_backups=args.list_backups,
    )

    if action == "tui":
        run_tui(args, context)
    else:
        run_cli(action, targets, args, context, parser)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Операция прервана пользователем (Ctrl+C).", file=sys.stderr)
        sys.exit(130)
    except DeployEngineError as err:
        print(f"\n❌ Ошибка: {err}", file=sys.stderr)
        sys.exit(1)
