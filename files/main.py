#!/usr/bin/env python3
"""
main.py: Единая точка входа Deploy Engine v3.0.0 (CLI + TUI).
- При запуске с CLI-командой (install, uninstall, reinstall, upgrade, backup, restore, list, info, config, scan, help) работает как CLI.
- При запуске без CLI-команды или с флагом --tui (-u) открывает интерактивный TUI-интерфейс.
- Обеспечивает сквозной перехват KeyboardInterrupt (Ctrl+C) с кодом выхода 130 без стектрейса.
"""
import argparse
import os
import sys
from typing import List, Optional, Tuple

from lib.config import DEFAULT_REMOTE_ENGINE_DIR
from lib.core.cli_dispatcher import dispatch_cli, load_engine_sources
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.remote.remote_deployer import RemoteDeployer
from lib.utils import bootstrap_gui

VALID_ACTIONS = {
    "install", "uninstall", "reinstall", "upgrade",
    "backup", "restore", "list", "info", "config",
    "completion", "scan", "tui", "version", "help",
}


def build_parser() -> argparse.ArgumentParser:
    """Создает единый парсер аргументов командной строки для CLI и TUI."""
    parser = argparse.ArgumentParser(
        prog="deploy-engine",
        description=(
            "Deploy Engine v3.0.0: Модульный кроссплатформенный оркестратор пакетов.\n"
            "• Запуск без команды (или с флагом --tui) открывает интерактивный TUI-интерфейс.\n"
            "• Запуск с командой (install, uninstall, reinstall, upgrade, backup, restore, list, info, config, scan) работает в CLI-режиме."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("pos_args", nargs="*", help="Команда (install|uninstall|reinstall|upgrade|backup|restore|list|info|config|scan|tui) и цели (<pkg> или <pkg>:<unit>)")
    parser.add_argument("--version", "-V", dest="show_version", action="store_true", help="Показать версию Deploy Engine и выйти")
    parser.add_argument("--tui", "-u", dest="force_tui", action="store_true", help="Принудительно открыть интерактивный TUI-интерфейс")
    parser.add_argument("--info", "-i", dest="info_flag", nargs="?", const="__FLAG_ONLY__", default=None, help="Показать описание пакета, статус и пути установки")
    parser.add_argument("--preset", dest="preset", action="store_true", help="Открыть/показать файл предустановки из внутреннего хранилища (для config)")
    parser.add_argument("--show", dest="show_config", action="store_true", help="Показать развернутую конфигурацию .env с актуальными подстановками #AUTO# (для config)")
    parser.add_argument("--reveal", dest="reveal", action="store_true", help="Показать секреты без маскирования (вместе с config --show)")
    parser.add_argument("--only", dest="only_units", default=None, help="Точечное обновление выбранных юнитов через запятую (например: --only web,files)")
    parser.add_argument("--unit-type", dest="unit_type", default=None, help="Точечное обновление юнитов указанного типа (web, file, script, unit, env, data, symlink)")
    parser.add_argument("--with-hooks", dest="with_hooks", action="store_true", help="Выполнить post_install хуки даже при точечном обновлении отдельных юнитов")
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
    parser.add_argument("--yes", "-y", dest="non_interactive", action="store_true", help="Неинтерактивный режим (значения .env по умолчанию)")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Вывод информации в формате JSON")
    parser.add_argument("--verbose", "-v", dest="verbose", action="store_true", help="Подробный отладочный вывод")
    return parser


def resolve_mode_and_targets(args: argparse.Namespace) -> Tuple[str, List[str]]:
    """Определяет режим работы ('tui' или имя CLI-действия), источник манифестов и список целевых пакетов."""
    if getattr(args, "show_version", False):
        return "version", []

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


def run_tui(args: argparse.Namespace, context: ExecutionContext) -> None:
    """Запускает интерактивный TUI-интерфейс (локально, в песочнице или в режиме Remote TUI)."""
    bootstrap_gui()
    from lib.ui.plan_executor import PlanExecutor
    from lib.ui_app import DeployApp

    context.in_tui = True
    engine = Engine(context)
    load_engine_sources(engine, args, "tui", [])

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
    context.in_tui = False

    if actions_plan and isinstance(actions_plan, dict):
        PlanExecutor.execute_plan(engine, actions_plan, remote_deployer=remote_deployer)


def run_cli(action: str, targets: List[str], args: argparse.Namespace, context: ExecutionContext, parser: argparse.ArgumentParser) -> None:
    """Обертка для обратной совместимости тестов и вызовов CLI."""
    dispatch_cli(action, targets, args, context, parser)


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
        non_interactive=args.non_interactive,
        rescan=args.rescan,
        json_output=args.json_output,
        sandbox=bool(args.sandbox_os is not None or args.sandbox_dir is not None),
        sandbox_os=args.sandbox_os,
        sandbox_dir=args.sandbox_dir,
        comment=args.comment,
        backup_selector=args.backup_selector,
        list_backups=args.list_backups,
        in_tui=(action == "tui"),
    )

    if action == "tui":
        run_tui(args, context)
    else:
        dispatch_cli(action, targets, args, context, parser)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❗ Операция прервана пользователем (Ctrl+C).", file=sys.stderr)
        sys.exit(130)
    except DeployEngineError as err:
        print(f"\n❌ Ошибка: {err}", file=sys.stderr)
        sys.exit(1)
