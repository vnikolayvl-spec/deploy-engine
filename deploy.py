#!/usr/bin/env python3
import sys
from lib.utils import check_root
from lib.engine import Engine

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование CLI:")
        print("  sudo ./deploy.py [путь_к_manifest.json] install [имя_пакета]")
        print("  sudo ./deploy.py [путь_к_manifest.json] uninstall [имя_пакета]")
        print("  sudo ./deploy.py [путь_к_manifest.json] reinstall [имя_пакета]")
        sys.exit(0)

    manifest_arg = sys.argv[1]
    
    # Разбираем экшены
    action = "install"
    targets = []
    
    if len(sys.argv) > 2:
        possible_action = sys.argv[2]
        if possible_action in ["install", "uninstall", "reinstall"]:
            action = possible_action
            targets = sys.argv[3:]
        else:
            targets = sys.argv[2:]

    engine = Engine()
    check_root()
    engine.load_manifest_recursive(manifest_arg)

    if not targets:
        print("❌ Ошибка: Не указано имя пакета для операции.")
        sys.exit(1)

    for target in targets:
        if action == "install":
            engine.resolve_dependencies(target)
            if engine.files_to_deploy:
                engine.install_files()
                
        elif action == "uninstall":
            engine.uninstall_package(target)
            
        elif action == "reinstall":
            print(f"\n🔄 Запуск процесса полной переустановки пакета: {target.upper()}")
            # 1. Сначала сносим старое
            engine.uninstall_package(target)
            # 2. Очищаем стек деплоера и накатываем заново
            engine.files_to_deploy.clear()
            engine.active_packages.clear()
            engine.deployed_file_paths.clear()
            
            engine.resolve_dependencies(target)
            if engine.files_to_deploy:
                engine.install_files()

