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
        try:
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
        except KeyboardInterrupt:
            print("\n⚠️ Инициализация графического окружения прервана пользователем (Ctrl+C).", file=sys.stderr)
            sys.exit(130)


RU_TO_EN_KEYMAP = str.maketrans(
    "йцукенгшщзхъфывапролджэячсмитьбюёЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮЁ",
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.`QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>~",
)


def normalize_hotkey(key: str, character: str = "") -> str:
    """Преобразует символ или название клавиши из русской раскладки (ЙЦУКЕН) в латинский аналог (QWERTY)."""
    if character and len(character) == 1:
        mapped_char = character.translate(RU_TO_EN_KEYMAP)
        if mapped_char != character:
            return mapped_char
    if key and len(key) == 1:
        return key.translate(RU_TO_EN_KEYMAP)
    return key or ""


def dispatch_localized_binding(app_instance, event) -> bool:
    """
    Универсальный диспетчер хоткеев: если нажата клавиша в русской раскладке,
    ищет соответствующий латинский биндинг в BINDINGS активного экрана или приложения и вызывает его action.
    """
    raw_key = getattr(event, "key", "") or ""
    raw_char = getattr(event, "character", "") or ""
    norm_key = normalize_hotkey(raw_key, raw_char)
    if not norm_key or norm_key == raw_key:
        return False

    targets = []
    scr = getattr(app_instance, "screen", None)
    if scr is not None and scr is not app_instance:
        targets.append(scr)
    targets.append(app_instance)

    for target in targets:
        for binding in getattr(target, "BINDINGS", ()) or ():
            b_key = binding[0] if isinstance(binding, (tuple, list)) else getattr(binding, "key", "")
            b_act = binding[1] if isinstance(binding, (tuple, list)) else getattr(binding, "action", "")
            if str(b_key).lower() == norm_key.lower() and b_act:
                handler = getattr(target, f"action_{b_act}", None)
                if callable(handler):
                    if hasattr(event, "prevent_default"):
                        event.prevent_default()
                    if hasattr(event, "stop"):
                        event.stop()
                    handler()
                    return True
    return False


