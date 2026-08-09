#!/usr/bin/env python3
import sys
import os

# КРИТИЧЕСКИЙ ФИЛЬТР CLI: Если передано много аргументов и второй аргумент существует,
# значит пользователь пытается вызвать CLI режим (например: ./deploy_ui.py manifest.json packet)
# или через packages.json (например: ./deploy_ui.py packet1 packet2).
# Мы сразу перенаправляем выполнение в чистый deploy.py
if len(sys.argv) > 1:
    # Если аргументов больше двух, или единственный аргумент не является файлом манифеста
    if len(sys.argv) > 2 or not sys.argv[1].endswith('.json'):
        os.execv(sys.executable, [sys.executable, "./deploy.py"] + sys.argv[1:])

# Запускаем автоматическую подготовку .venv и установку Textual, 
# только если мы железно находимся в режиме интерактивной графики (TUI)
from lib.utils import bootstrap_gui
bootstrap_gui()

# Импортируем бэкенд и фронтенд (доступно, так как мы уже внутри .venv)
from lib.engine import Engine
from lib.ui_app import DeployApp

if __name__ == "__main__":
    engine = Engine()
    
    # Проверяем, передан ли аргумент-путь для графики
    if len(sys.argv) > 1 and sys.argv[1].endswith('.json'):
        # Если передан явный манифест, загружаем его
        engine.load_manifest_recursive(sys.argv[1])
    else:
        # Если запущено просто как `sudo ./deploy_ui.py`, активируем реестр packages.json
        engine.load_default_manifests()
    
    # Инициализируем и запускаем графическое приложение Textual
    app = DeployApp(engine)
    selected_components = app.run()
    
    # Если в интерфейсе нажали кнопку «Установить» и выбрали компоненты
    if selected_components:
        engine.files_to_deploy.clear()
        for t in selected_components: 
            engine.resolve_dependencies(t)
        engine.install_files()
