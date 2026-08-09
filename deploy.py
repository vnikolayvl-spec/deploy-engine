#!/usr/bin/env python3
import sys
from lib.utils import check_root
from lib.engine import Engine

if __name__ == "__main__":
    engine = Engine()
    check_root()

    # Проверяем, переданы ли аргументы командной строки
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        
        # Если первый аргумент явно указывает на файл манифеста JSON
        if first_arg.endswith('.json'):
            # Загружаем указанный манифест
            engine.load_manifest_recursive(first_arg)
            # Все последующие аргументы — это пакеты для установки
            targets = sys.argv[2:]
        else:
            # Иначе первый аргумент — это уже имя пакета. 
            # Загружаем реестр по умолчанию из packages.json
            engine.load_default_manifests()
            # Все аргументы с самого первого считаем целями для установки
            targets = sys.argv[1:]
    else:
        # Если скрипт запущен вообще без аргументов, выводим краткую справку
        print("Использование CLI:")
        print("  С явным манифестом: sudo ./deploy.py [путь_к_manifest.json] [пакет1] [пакет2] ...")
        print("  Через packages.json: sudo ./deploy.py [пакет1] [пакет2] ...")
        print("\nЗапустите './deploy_ui.py' для вызова интерактивного графического интерфейса.")
        sys.exit(0)

    # Если цели для установки переданы, запускаем сбор зависимостей и деплой
    if targets:
        for target in targets:
            engine.resolve_dependencies(target)
            
        if engine.files_to_deploy:
            engine.install_files()
    else:
        print("⚠️ Предупреждение: Манифесты загружены, но не указаны пакеты для установки.")
