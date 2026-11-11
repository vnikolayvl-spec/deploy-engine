#!/usr/bin/env python3
import os
import sys

# Перенаправляем в CLI режим, если аргументов много
if len(sys.argv) > 2:
    os.execv(sys.executable, [sys.executable, "./deploy.py"] + sys.argv[1:])

from lib.utils import bootstrap_gui
bootstrap_gui()

from lib.engine import Engine
from lib.ui_app import DeployApp

if __name__ == "__main__":
    source_arg = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else None

    engine = Engine()
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
        print("Использование TUI: sudo ./deploy_ui.py [путь_к_папке_пакетов | путь_к_manifest.json]")
        sys.exit(0)

    app = DeployApp(engine)
    actions_plan = app.run()

    if actions_plan and isinstance(actions_plan, dict):
        to_uninstall = [k for k, v in actions_plan.items() if v == "uninstall" and engine.registry.has(k)]
        to_reinstall = [k for k, v in actions_plan.items() if v == "reinstall" and engine.registry.has(k)]
        to_install = [k for k, v in actions_plan.items() if v == "install" and engine.registry.has(k)]

        # ЭТАП 1: Массовое удаление помеченных пакетов [-]
        for pkg in to_uninstall:
            engine.uninstall_package(pkg)

        # ЭТАП 2: Массовая чистая переустановка пакетов [↻]
        for pkg in to_reinstall:
            print(f"\n🔄 TUI: Запуск переустановки пакета: {pkg.upper()}")
            engine.reinstall_package(pkg)

        # ЭТАП 3: Накатка новых чистых пакетов [+]
        if to_install:
            engine.install_packages(to_install)
