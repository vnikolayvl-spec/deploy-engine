#!/usr/bin/env python3
import sys
import os

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
from lib.modules.state_manager import load_state

if __name__ == "__main__":
    manifest_arg = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith('.json') else None
    
    engine = Engine()
    if manifest_arg:
        engine.load_manifest_recursive(manifest_arg)
    else:
        engine.load_default_manifests()
    
    app = DeployApp(engine)
    selected_components = app.run()
    
    if selected_components:
        current_state = load_state()
        
        for target in selected_components:
            engine.files_to_deploy.clear()
            engine.active_packages.clear()
            engine.deployed_file_paths.clear()
            
            if target in current_state.get("installed_packages", {}):
                print(f"\n🔄 TUI: Запуск переустановки активного пакета: {target.upper()}")
                engine.uninstall_package(target)
                
                engine.resolve_dependencies(target)
                if engine.files_to_deploy:
                    engine.install_files()
            else:
                engine.resolve_dependencies(target)
                if engine.files_to_deploy:
                    engine.install_files()

