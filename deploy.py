#!/usr/bin/env python3
"""
Deploy Engine CLI Interface with cross-platform providers and optional --sandbox [target_os].
"""
import argparse
import os
import sys
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.remote.remote_deployer import RemoteDeployer
from lib.state.package_inspector import PackageInspector
from lib.utils import check_root

VALID_ACTIONS = {"install", "uninstall", "reinstall", "list", "info", "scan", "help"}


def build_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="deploy.py",
        description="Deploy Engine: Модульный кроссплатформенный оркестратор развертывания пакетов.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "action",
        nargs="?",
        default="help",
        choices=list(VALID_ACTIONS),
        help="Действие: install | uninstall | reinstall | list | info | scan",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Имена пакетов или пространств имен (необязательно, если указан манифест пакета)",
    )
    parser.add_argument(
        "--info",
        "-i",
        dest="info_flag",
        nargs="?",
        const="__FLAG_ONLY__",
        default=None,
        help="Показать описание пакета, статус и пути установки в системе",
    )
    parser.add_argument(
        "--manifest",
        "-m",
        dest="manifest",
        default=None,
        help="Путь к manifest.json пакета или к корневой папке дерева пакетов",
    )
    parser.add_argument(
        "--packages-dir",
        "-d",
        dest="packages_dir",
        default=None,
        help="Путь к папке-источнику дерева пакетов (папка может быть без собственного манифеста)",
    )
    parser.add_argument(
        "--sandbox",
        dest="sandbox_os",
        nargs="?",
        const="auto",
        default=None,
        help="Тестовый режим песочницы с опциональным выбором эмулируемой ОС (debian, ubuntu, alpine, arch, macos)",
    )
    parser.add_argument(
        "--sandbox-dir",
        dest="sandbox_dir",
        default=None,
        help="Путь к директории локальной песочницы (по умолчанию ./.de_sandbox)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        dest="dry_run",
        action="store_true",
        help="Симуляция установки без модификации файлов и системы",
    )
    parser.add_argument(
        "--purge",
        dest="purge",
        action="store_true",
        help="Полное удаление каталогов ENV и Data при удалении",
    )
    parser.add_argument(
        "--clean-env",
        dest="clean_env",
        action="store_true",
        help="Сброс переменных окружения к заводским настройкам (перезапись)",
    )
    parser.add_argument(
        "--rescan",
        dest="rescan",
        action="store_true",
        help="Принудительный переобход директорий и обновление кэша packages.json",
    )
    parser.add_argument(
        "--remote",
        "-r",
        dest="remote",
        default=None,
        help="Удаленный хост для выполнения операции [user@]host[:port]",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Вывод информации в формате JSON (для списков и инспекции)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        dest="verbose",
        action="store_true",
        help="Подробный отладочный вывод",
    )

    return parser


def parse_legacy_arguments(raw_args):
    """
    Поддержка позиционного указания манифеста, папки пакетов или имени пакета с --info:
    deploy.py <manifest_path_or_dir_or_pkg> [action] [targets_and_flags...]
    """
    if len(raw_args) >= 1 and raw_args[0] not in VALID_ACTIONS and not raw_args[0].startswith("-"):
        if raw_args[0].endswith(".json") or os.path.exists(raw_args[0]):
            manifest_or_dir = raw_args[0]
            remaining = raw_args[1:]
            action = "info" if ("--info" in remaining or "-i" in remaining) else "install"
            filtered_remaining = []
            found_action = False
            for token in remaining:
                if not found_action and token in VALID_ACTIONS:
                    action = token
                    found_action = True
                else:
                    filtered_remaining.append(token)
            return manifest_or_dir, action, filtered_remaining
        if "--info" in raw_args or "-i" in raw_args:
            return None, "info", raw_args
    return None, None, None


def main():
    raw_args = sys.argv[1:]

    legacy_source, legacy_action, legacy_rest = parse_legacy_arguments(raw_args)
    parser = build_parser()

    if legacy_source:
        args = parser.parse_args([legacy_action] + legacy_rest)
        if os.path.isdir(legacy_source):
            args.packages_dir = legacy_source
        else:
            args.manifest = legacy_source
    elif legacy_action == "info":
        args = parser.parse_args(["info"] + legacy_rest)
    else:
        args = parser.parse_args()

    if args.info_flag is not None:
        args.action = "info"
        if args.info_flag != "__FLAG_ONLY__" and args.info_flag not in args.targets:
            args.targets.insert(0, args.info_flag)

    if args.action == "help" or (not raw_args and args.action == "help"):
        parser.print_help()
        sys.exit(0)

    if not args.manifest and not args.packages_dir and len(args.targets) == 1:
        single_target = args.targets[0]
        if os.path.isfile(single_target) and single_target.endswith(".json"):
            args.manifest = single_target
            args.targets = []
        elif os.path.isdir(single_target) and args.action == "scan":
            args.packages_dir = single_target
            args.targets = []

    if args.manifest and os.path.isdir(args.manifest):
        args.packages_dir = args.manifest
        args.manifest = None

    context = ExecutionContext(
        dry_run=args.dry_run,
        purge=args.purge,
        clean_env=args.clean_env,
        verbose=args.verbose,
        remote=args.remote,
        rescan=args.rescan,
        json_output=args.json_output,
        sandbox=bool(args.sandbox_os is not None or args.sandbox_dir is not None),
        sandbox_os=args.sandbox_os,
        sandbox_dir=args.sandbox_dir,
    )

    engine = Engine(context)

    if args.manifest and not args.targets and args.action in ("install", "uninstall", "reinstall", "info"):
        inferred = engine.infer_targets_from_manifest(args.manifest)
        if inferred:
            args.targets = inferred

    if args.remote:
        deployer = RemoteDeployer(args.remote, context)
        if args.action == "list":
            state = deployer.fetch_remote_state()
            if args.json_output:
                import json
                print(json.dumps(state.get("installed", {}), indent=2, ensure_ascii=False))
            else:
                installed = state.get("installed", {})
                if not installed:
                    print(f"На удаленном хосте {args.remote} нет установленных пакетов.")
                else:
                    print(f"📦 Установленные пакеты на {args.remote}:")
                    for k, v in installed.items():
                        print(f"  • {k} (версия {v.get('version', 'N/A')})")
            return
        if not args.targets:
            print("❌ Ошибка: Укажите имена пакетов для удаленной операции.")
            sys.exit(1)
        deployer.execute_remote(args.targets, args.action)
        return

    if args.manifest:
        engine.load_manifest_recursive(args.manifest)
        if not args.targets and args.action in ("install", "uninstall", "reinstall", "info"):
            args.targets = engine.infer_targets_from_manifest(args.manifest)
    elif args.packages_dir:
        pkg_count = engine.discover_packages(search_roots=[args.packages_dir], force_rescan=True)
        if args.action == "scan":
            print(f"✅ База пакетов успешно обновлена из '{args.packages_dir}'. Обнаружено пакетов: {pkg_count} (сохранено в packages.json).")
            return
    else:
        pkg_count = engine.discover_packages(force_rescan=(args.action == "scan" or args.rescan))
        if args.action == "scan":
            print(f"✅ База пакетов успешно обновлена. Обнаружено пакетов: {pkg_count} (сохранено в packages.json).")
            return

    if args.action == "list":
        inspector = PackageInspector(state_repo=engine.state_repo, engine=engine)
        print(inspector.to_json() if args.json_output else inspector.format_table())
        return

    if args.action == "info":
        if not args.targets:
            print("❌ Ошибка: Укажите имя пакета для просмотра информации (например: deploy.py info <пакет> или deploy.py --info <пакет>).")
            sys.exit(1)
        inspector = PackageInspector(state_repo=engine.state_repo, engine=engine)
        if args.json_output:
            print(inspector.info_to_json(args.targets))
        else:
            print("\n\n".join(inspector.format_package_info(t) for t in args.targets))
        return

    if not args.targets:
        print(f"❌ Ошибка: Не указано имя пакета для операции '{args.action}'.")
        sys.exit(1)

    if not args.dry_run and engine.provider.requires_root():
        check_root()

    try:
        if args.action == "install":
            engine.install_packages(args.targets)
        elif args.action == "uninstall":
            for target in args.targets:
                engine.uninstall_package(target)
        elif args.action == "reinstall":
            for target in args.targets:
                engine.reinstall_package(target)
    except DeployEngineError as err:
        print(f"\n❌ Ошибка развертывания: {err}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ Операция прервана пользователем.")
        sys.exit(130)


if __name__ == "__main__":
    main()
