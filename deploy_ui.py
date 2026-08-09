#!/usr/bin/env python3
import sys
import os

# Перехват для CLI-режима: если передано много аргументов
if len(sys.argv) > 2:
    os.execv(sys.executable, [sys.executable, "./deploy.py"] + sys.argv[1:])

if len(sys.argv) == 1:
    print("Использование TUI: sudo ./deploy_ui.py [путь_к_manifest.json]")
    sys.exit(0)

# Запускаем подготовку графического окружения
from lib.utils import bootstrap_gui
bootstrap_gui()

# Импортируем бэкенд и фронтенд (доступно, так как мы уже внутри venv)
from lib.engine import Engine
from lib.ui_app import DeployApp

if __name__ == "__main__":
    manifest_arg = sys.argv[1]
    
    engine = Engine()
    engine.load_manifest_recursive(manifest_arg)
    
    app = DeployApp(engine)
    selected_components = app.run()
    
    if selected_components:
        engine.files_to_deploy.clear()
        for t in selected_components: 
            engine.resolve_dependencies(t)
        engine.install_files()
