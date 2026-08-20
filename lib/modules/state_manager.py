#!/usr/bin/env python3
"""
Модуль управления локальным реестром состояния (state.json),
безопасной деактивации служб systemd и зачистки диска от файлов пакета.
"""
import os
import json
import sys
import shutil
import subprocess
import deploy_config as config

def get_state_filepath():
    """Возвращает абсолютный путь к файлу реестра состояний"""
    return os.path.join(config.ENV_PATH, "state.json")

def load_state():
    """Загружает текущий реестр состояний с диска"""
    state_file = get_state_filepath()
    if not os.path.exists(state_file):
        return {"installed_packages": {}}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Предупреждение: Не удалось прочитать state.json: {e}")
        return {"installed_packages": {}}

def save_state(state_data):
    """Безопасно сохраняет реестр состояний на диск с правами 600"""
    state_file = get_state_filepath()
    try:
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        if os.path.exists(state_file):
            os.remove(state_file)
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2, ensure_ascii=False)
        os.chown(state_file, 0, 0)
        os.chmod(state_file, 0o600)
    except Exception as e:
        print(f"❌ Критическая ошибка записи state.json: {e}")
        sys.exit(1)

def register_package_install(pkg_name, deployed_files):
    """Фиксирует успешную установку пакета и список его файлов в реестре"""
    state_data = load_state()
    from datetime import datetime
    
    state_data["installed_packages"][pkg_name] = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": sorted(list(set(deployed_files)))
    }
    save_state(state_data)
    print(f"📝 Пакет '{pkg_name}' успешно зарегистрирован в реестре состояний.")

def execute_package_uninstall(pkg_name, engine):
    """
    Выполняет полную зачистку пакета: гасит systemd, 
    удаляет файлы и стирает песочницу пакета.
    """
    state_data = load_state()
    if pkg_name not in state_data["installed_packages"]:
        print(f"❌ Ошибка: Пакет '{pkg_name}' не найден в реестре установленных программ.")
        return False

    pkg_state = state_data["installed_packages"][pkg_name]
    files_to_remove = pkg_state.get("files", [])

    print("\n" + "="*50)
    print(f"🧹 ЗАПУСК СИСТЕМНОЙ ЗАЧИСТКИ ПАКЕТА: {pkg_name.upper()}")
    print("="*50)

    # 1. Сначала ищем и безопасно останавливаем службы systemd
    services_to_disable = []
    for filepath in files_to_remove:
        if filepath.startswith(config.SYS_SYSTEMD) and filepath.endswith(('.service', '.timer')):
            services_to_disable.append(os.path.basename(filepath))

    if services_to_disable:
        print("🛑 Останавливаем и отключаем связанные службы systemd...")
        for svc in sorted(services_to_disable):
            print(f"   -> systemctl disable --now {svc}")
            subprocess.run(["systemctl", "disable", "--now", svc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Физически удаляем все файлы и симлинки, созданные этим пакетом
    print("🗑️ Удаляем исполняемые файлы и симлинки...")
    for filepath in sorted(files_to_remove):
        if os.path.exists(filepath) or os.path.islink(filepath):
            print(f"   -> Удаление: {filepath}")
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"      ⚠️ Ошибка удаления файла {filepath}: {e}")

    # 3. Полностью удаляем изолированную песочницу секретов этого пакета
    sandbox_folder_name = f"{config.ENV_PREFIX}{pkg_name}"
    sandbox_dir = os.path.join(config.ENV_PATH, sandbox_folder_name)
    if os.path.exists(sandbox_dir):
        print(f"📂 Зачищаем папку окружения секретов: {sandbox_dir}")
        try:
            shutil.rmtree(sandbox_dir)
        except Exception as e:
            print(f"   ⚠️ Ошибка удаления папки {sandbox_dir}: {e}")

    # 4. Стираем запись о пакете из общего реестра
    del state_data["installed_packages"][pkg_name]
    save_state(state_data)

    print("\n🔄 Перезагрузка демона systemd (daemon-reload)...")
    subprocess.run(["systemctl", "daemon-reload"])
    print(f"🎉 Пакет '{pkg_name}' полностью и бесследно удален из системы!")
    return True

