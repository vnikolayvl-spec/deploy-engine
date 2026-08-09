#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import deploy_config as config

def check_root():
    """Атомарная проверка прав root"""
    if os.geteuid() != 0:
        print("❌ Ошибка: Запустите скрипт через sudo!")
        sys.exit(1)

def bootstrap_gui():
    """Проверяет окружение, создает venv, ставит Textual и перезапускает скрипт"""
    check_root()
    
    in_venv = sys.prefix == os.path.abspath(config.VENV_PATH)
    if not in_venv:
        print("🔄 Проверка графического окружения...")
        if not os.path.exists(config.VENV_PATH):
            print("📦 Создание виртуального окружения (.venv)...")
            try:
                subprocess.run([sys.executable, "-m", "venv", config.VENV_PATH], check=True)
            except subprocess.CalledProcessError:
                subprocess.run(["apt-get", "update"])
                subprocess.run(["apt-get", "install", "-y", "python3-venv", "python3-pip"])
                subprocess.run([sys.executable, "-m", "venv", config.VENV_PATH], check=True)
            
        venv_python = os.path.join(config.VENV_PATH, "bin", "python")
        print("📥 Доставка графической библиотеки Textual...")
        subprocess.run([venv_python, "-m", "pip", "install", "--upgrade", "pip"], stdout=subprocess.DEVNULL)
        subprocess.run([venv_python, "-m", "pip", "install", "textual[dev]"], stdout=subprocess.DEVNULL)
        
        print("🚀 Запуск графического интерфейса...")
        os.execv(venv_python, [venv_python] + sys.argv)
