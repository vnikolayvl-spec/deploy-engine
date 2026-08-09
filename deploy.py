#!/usr/bin/env python3
import sys
from lib.utils import check_root
from lib.engine import Engine

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: sudo ./deploy.py [путь_к_manifest.json] [пакет_или_файл1] ...")
        sys.exit(0)

    engine = Engine()
    check_root()
    engine.load_manifest_recursive(sys.argv[1])

    for target in sys.argv[2:]:
        engine.resolve_dependencies(target)
        
    if engine.files_to_deploy:
        engine.install_files()
