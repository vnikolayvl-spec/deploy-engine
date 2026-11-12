#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import lib.config as config

def check_root():
    """Атомарная проверка прав root"""
    if os.geteuid() != 0:
        print("❌ Ошибка: Запустите скрипт через sudo!")
        sys.exit(1)

def bootstrap_gui():
    """Проверяет окружение, создает venv, ставит Textual и перезапускает скрипт"""
    if "--sandbox" not in sys.argv and "--dry-run" not in sys.argv and "-n" not in sys.argv and "--remote" not in sys.argv and "-r" not in sys.argv:
        check_root()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    engine_root = os.path.dirname(script_dir)
    parent_venv = os.path.join(os.path.dirname(engine_root), ".venv")
    venv_path = parent_venv if os.path.exists(os.path.join(parent_venv, "bin", "python")) else os.path.join(engine_root, ".venv")
    
    in_venv = os.path.abspath(sys.prefix) == os.path.abspath(venv_path)
    if not in_venv:
        print("🔄 Проверка графического окружения...")
        venv_python = os.path.join(venv_path, "bin", "python")

        # Проверка работоспособности существующего venv и pip
        venv_valid = False
        if os.path.exists(venv_python):
            test_pip = subprocess.run([venv_python, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if test_pip.returncode == 0:
                venv_valid = True

        if not venv_valid:
            if os.path.exists(venv_path):
                shutil.rmtree(venv_path, ignore_errors=True)

            print("📦 Создание виртуального окружения (.venv)...")
            created = False
            try:
                subprocess.run([sys.executable, "-m", "venv", venv_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                created = True
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

            # Если ensurepip/venv отсутствует в системе (Debian/Ubuntu без python3-venv)
            if not created or not os.path.exists(venv_python):
                if shutil.which("apt-get"):
                    print("📦 Установка системных пакетов python3-venv и python3-pip...")
                    os.environ["DEBIAN_FRONTEND"] = "noninteractive"
                    subprocess.run(["apt-get", "update", "-y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(["apt-get", "install", "-y", "python3-venv", "python3-pip", "python3-full"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif shutil.which("yum"):
                    subprocess.run(["yum", "install", "-y", "python3-pip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if os.path.exists(venv_path):
                    shutil.rmtree(venv_path, ignore_errors=True)
                subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)

        print("📥 Доставка графической библиотеки Textual...")
        subprocess.run([venv_python, "-m", "pip", "install", "--no-cache-dir", "--upgrade", "pip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([venv_python, "-m", "pip", "install", "--no-cache-dir", "textual-dev", "textual"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print("🚀 Запуск графического интерфейса...")
        os.execv(venv_python, [venv_python] + sys.argv)

