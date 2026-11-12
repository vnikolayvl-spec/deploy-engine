#!/usr/bin/env python3
"""
Deploy Engine TUI launcher supporting cross-platform providers and optional --sandbox [target_os].
"""
import argparse
import os
import sys

from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext
from lib.utils import bootstrap_gui

bootstrap_gui()

from lib.engine import Engine
from lib.ui_app import DeployApp


def parse_tui_args():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("source", nargs="?", default=None)
    parser.add_argument("--sandbox", dest="sandbox_os", nargs="?", const="auto", default=None)
    parser.add_argument("--sandbox-dir", dest="sandbox_dir", default=None)
    parser.add_argument("--dry-run", "-n", dest="dry_run", action="store_true")
    return parser.parse_known_args()


if __name__ == "__main__":
    args, unknown = parse_tui_args()
    cli_tokens = {"install", "uninstall", "reinstall", "list", "info", "scan", "--info", "-i"}
    if (args.source in cli_tokens) or (unknown and any(u in cli_tokens for u in unknown)):
        os.execv(sys.executable, [sys.executable, "./deploy.py"] + sys.argv[1:])

    ctx = ExecutionContext(
        dry_run=args.dry_run,
        sandbox=bool(args.sandbox_os is not None or args.sandbox_dir is not None),
        sandbox_os=args.sandbox_os,
        sandbox_dir=args.sandbox_dir,
    )
    engine = Engine(ctx)

    source_arg = args.source
    if source_arg:
        if os.path.isdir(source_arg):
            engine.discover_packages(search_roots=[source_arg], force_rescan=True)
        elif os.path.isfile(source_arg):
            engine.load_manifest_recursive(source_arg)
        else:
            print(f"❌ Ошибка: Источник '{source_arg}' не найден.")
            sys.exit(1)
    else:
        engine.load_default_manifests()

    if not engine.packages and not getattr(engine, "folders", {}):
        print("Использование TUI: ./deploy_ui.py [путь_к_папке | путь_к_manifest.json] [--sandbox [debian|macos]]")
        sys.exit(0)

    app = DeployApp(engine)
    actions_plan = app.run()

    if actions_plan and isinstance(actions_plan, dict):
        to_uninstall = [k for k, v in actions_plan.items() if v == "uninstall" and engine.registry.has(k)]
        to_reinstall = [k for k, v in actions_plan.items() if v == "reinstall" and engine.registry.has(k)]
        to_install = [k for k, v in actions_plan.items() if v == "install" and engine.registry.has(k)]

        try:
            for pkg in to_uninstall:
                engine.uninstall_package(pkg)
            for pkg in to_reinstall:
                print(f"\n🔄 TUI: Запуск переустановки пакета: {pkg.upper()}")
                engine.reinstall_package(pkg)
            if to_install:
                engine.install_packages(to_install)
        except DeployEngineError as err:
            print(f"\n❌ Ошибка развертывания: {err}")
            sys.exit(1)
