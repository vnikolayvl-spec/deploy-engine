#!/usr/bin/env python3
"""
Deploy Engine 2.0 CLI Interface.
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


def build_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="deploy.py",
        description="Deploy Engine 2.0: Модульный автономный оркестратор развертывания пакетов.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "action",
        nargs="?",
        default="help",
        choices=["install", "uninstall", "reinstall", "list", "scan", "help"],
        help="Действие: install | uninstall | reinstall | list | scan",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Имена пакетов или пространств имен для выполнения операции",
    )
    parser.add_argument(
        "--manifest",
        "-m",
        dest="manifest",
        default=None,
        help="Путь к конкретному файлу manifest.json (режим обратной совместимости)",
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
        help="Полное удаление каталогов ENV и Data (/var/lib/de_{pkg}) при удалении",
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
    Поддержка старого синтаксиса:
    deploy.py [manifest_path] [action] [targets...]
    """
    if len(raw_args) >= 1 and (raw_args[0].endswith(".json") or os.path.exists(raw_args[0])):
        manifest_file = raw_args[0]
        remaining = raw_args[1:]
        action = "install"
        targets = []
        if remaining:
            if remaining[0] in ["install", "uninstall", "reinstall", "list", "scan"]:
                action = remaining[0]
                targets = remaining[1:]
            else:
                targets = remaining
        return manifest_file, action, targets
    return None, None, None


def main():
    raw_args = sys.argv[1:]

    # Проверяем старый синтаксис
    legacy_manifest, legacy_action, legacy_targets = parse_legacy_arguments(raw_args)
    parser = build_parser()

    if legacy_manifest:
        args = parser.parse_args(legacy_targets)
        args.action = legacy_action
        args.manifest = legacy_manifest
        args.targets = legacy_targets
    else:
        args = parser.parse_args()

    if args.action == "help" or (not raw_args and args.action == "help"):
        parser.print_help()
        sys.exit(0)

    # Инициализация контекста
    context = ExecutionContext(
        dry_run=args.dry_run,
        purge=args.purge,
        clean_env=args.clean_env,
        verbose=args.verbose,
        remote=args.remote,
        rescan=args.rescan,
        json_output=args.json_output,
    )

    # Удаленный режим через SSH
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
        else:
            if not args.targets:
                print("❌ Ошибка: Укажите имена пакетов для удаленной операции.")
                sys.exit(1)
            deployer.execute_remote(args.targets, args.action)
            return

    # Локальная инспекция установленных пакетов (не требует root)
    if args.action == "list":
        inspector = PackageInspector()
        if args.json_output:
            print(inspector.to_json())
        else:
            print(inspector.format_table())
        return

    # Сканирование и обновление базы пакетов packages.json (не требует root)
    engine = Engine(context)

    if args.manifest:
        engine.load_manifest_recursive(args.manifest)
    else:
        pkg_count = engine.discover_packages(force_rescan=(args.action == "scan" or args.rescan))
        if args.action == "scan":
            print(f"✅ База пакетов успешно обновлена. Обнаружено пакетов: {pkg_count} (сохранено в packages.json).")
            return

    if not args.targets:
        print(f"❌ Ошибка: Не указано имя пакета для операции '{args.action}'.")
        sys.exit(1)

    # Проверка root для реальных операций изменения локальной системы
    if not args.dry_run:
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
