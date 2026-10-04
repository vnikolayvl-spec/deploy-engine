#!/usr/bin/env python3
"""
Модуль управления локальным реестром состояния (state.json),
автогенерации паспорта пакета pack.env и безопасной зачистки.
"""
import os
import json
import sys
import shutil
import subprocess
import deploy_config as config

def get_state_filepath():
    return os.path.join(config.ENV_PATH, "state.json")

def load_state():
    state_file = get_state_filepath()
    if not os.path.exists(state_file):
        return {"installed_packages": {}}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"installed_packages": {}}

def save_state(state_data):
    state_file = get_state_filepath()
    try:
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        if os.path.exists(state_file): os.remove(state_file)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
        os.chown(state_file, 0, 0)
        os.chmod(state_file, 0o600)
    except Exception as e:
        print(f"❌ Ошибка записи state.json: {e}"); sys.exit(1)

def generate_pack_env(pkg_name, files_map):
    """Генерирует pack.env паспорт с классификацией путей по типам Bash-массивов"""
    sandbox_dir = os.path.join(config.ENV_PATH, f"{config.ENV_PREFIX}{pkg_name}")
    pack_env_path = os.path.join(sandbox_dir, "pack.env")
    
    scripts, timers, units, files = [], [], [], []
    
    for filepath, f_type in files_map.items():
        if f_type == "script" or filepath.startswith(config.SYS_BIN):
            scripts.append(f'"{filepath}"')
        elif f_type == "timer" or filepath.endswith(".timer"):
            timers.append(f'"{filepath}"')
        elif f_type in ["unit", "service"] or (filepath.startswith(config.SYS_SYSTEMD) and filepath.endswith(".service")):
            units.append(f'"{filepath}"')
        else:
            files.append(f'"{filepath}"')

    try:
        os.makedirs(sandbox_dir, exist_ok=True)
        if os.path.exists(pack_env_path):
            os.remove(pack_env_path)
            
        with open(pack_env_path, "w", encoding="utf-8") as f:
            f.write("# Автогенерация Deploy Engine. Паспорт развернутых ресурсов пакета.\n")
            f.write(f"SCRIPTS=({' '.join(scripts)})\n")
            f.write(f"TIMERS=({' '.join(timers)})\n")
            f.write(f"UNITS=({' '.join(units)})\n")
            f.write(f"FILES=({' '.join(files)})\n")
            
        os.chown(pack_env_path, 0, 0)
        os.chmod(pack_env_path, 0o600)
        print(f"📝 Паспорт пакета успешно сгенерирован по пути: {pack_env_path}")
    except Exception as e:
        print(f"⚠️ Ошибка автогенерации pack.env: {e}")

def register_package_install(pkg_name, deployed_files_map):
    """Записывает успешную установку в state.json и вызывает сборку pack.env"""
    state_data = load_state()
    from datetime import datetime
    
    state_data["installed_packages"][pkg_name] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": sorted(list(deployed_files_map.keys()))
    }
    save_state(state_data)
    
    # Запускаем сборку паспорта ресурсов
    generate_pack_env(pkg_name, deployed_files_map)
    print(f"📝 Пакет '{pkg_name}' успешно зарегистрирован в реестре состояний.")

def execute_package_uninstall(pkg_name, engine):
    state_data = load_state()
    if pkg_name not in state_data["installed_packages"]:
        print(f"❌ Пакет '{pkg_name}' не найден в реестре."); return False

    pkg_state = state_data["installed_packages"][pkg_name]
    files_to_remove = pkg_state.get("files", [])

    print("\n" + "="*50)
    print(f"🧹 СИСТЕМНАЯ ЗАЧИСТКА ПАКЕТА: {pkg_name.upper()}")
    print("="*50)

    # 1. Глушим службы systemd
    services_to_disable = [os.path.basename(f) for f in files_to_remove if f.startswith(config.SYS_SYSTEMD)]
    if services_to_disable:
        for svc in sorted(services_to_disable):
            subprocess.run(["systemctl", "disable", "--now", svc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Удаляем файлы и симлинки
    for filepath in sorted(files_to_remove):
        if os.path.exists(filepath) or os.path.islink(filepath):
            try: os.remove(filepath)
            except Exception: pass

    # 3. Полностью сносим всю песочницу (включая env и pack.env)
    sandbox_dir = os.path.join(config.ENV_PATH, f"{config.ENV_PREFIX}{pkg_name}")
    if os.path.exists(sandbox_dir):
        try: shutil.rmtree(sandbox_dir)
        except Exception: pass

    del state_data["installed_packages"][pkg_name]
    save_state(state_data)
    subprocess.run(["systemctl", "daemon-reload"])
    print(f"🎉 Пакет '{pkg_name}' полностью удален из Linux!")
    return True

