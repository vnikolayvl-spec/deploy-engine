#!/usr/bin/env python3
import sys
import os

# Перенаправляем в CLI режим, если аргументов много
if len(sys.argv) > 2:
    os.execv(sys.executable, [sys.executable, "./deploy.py"] + sys.argv[1:])

if len(sys.argv) == 1:
    from lib.engine import Engine
    test_eng = Engine()
    if not os.path.exists("./packages.json"):
        print("Использование TUI: sudo ./deploy_ui.py [путь_к_manifest.json]")
        sys.exit(0)

from lib.utils import bootstrap_gui
bootstrap_gui()

from lib.engine import Engine
from lib.ui_app import DeployApp

if __name__ == "__main__":
    # Проверяем расширение у конкретного аргумента-строки, а не у списка argv
    manifest_arg = sys.argv if len(sys.argv) > 1 and sys.argv[1].endswith('.json') else None
    
    engine = Engine()
    if manifest_arg:
        engine.load_manifest_recursive(manifest_arg[1])
    else:
        engine.load_default_manifests()
    
    app = DeployApp(engine)
    actions_plan = app.run()
    
    if actions_plan and isinstance(actions_plan, dict):
        # ФИЛЬТР: Распределяем задачи СТРОГО для пакетов, игнорируя отдельные файлы-листья
        to_uninstall = [k for k, v in actions_plan.items() if v == "uninstall" and k in engine.packages]
        to_reinstall = [k for k, v in actions_plan.items() if v == "reinstall" and k in engine.packages]
        to_install = [k for k, v in actions_plan.items() if v == "install" and k in engine.packages]

        # ЭТАП 1: Массовое удаление помеченных пакетов [-]
        for pkg in to_uninstall:
            engine.uninstall_package(pkg)

        # ЭТАП 2: Массовая чистая переустановка пакетов [↻]
        for pkg in to_reinstall:
            print(f"\n🔄 TUI: Запуск переустановки пакета: {pkg.upper()}")
            engine.uninstall_package(pkg)
            
            engine.files_to_deploy.clear()
            engine.active_packages.clear()
            engine.deployed_files_map.clear()  # Исправлено
            
            engine.resolve_dependencies(pkg)
            if engine.files_to_deploy:
                engine.install_files()

        # ЭТАП 3: Накатка новых чистых пакетов [X]
        for pkg in to_install:
            engine.files_to_deploy.clear()
            engine.active_packages.clear()
            engine.deployed_files_map.clear()  # Исправлено
            
            engine.resolve_dependencies(pkg)
            if engine.files_to_deploy:
                engine.install_files()

