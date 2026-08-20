#!/usr/bin/env python3
import shutil
import subprocess
import sys

def install_system_dependencies(packages_list):
    """
    Автоматически определяет менеджер пакетов ОС (APT или YUM) 
    и устанавливает переданный список системных утилит.
    """
    if not packages_list:
        return

    # Очищаем список от дубликатов и пустых строк
    unique_packages = sorted(list(set([p.strip() for p in packages_list if p.strip()])))
    if not unique_packages:
        return

    print("\n" + "-"*50)
    print(f"📦 [ОС] Проверка и установка системных пакетов: {', '.join(unique_packages)}")
    print("-"*50)

    # Определяем менеджер пакетов в системе
    if shutil.which("apt-get"):
        cmd_update = ["apt-get", "update", "-y"]
        cmd_install = ["apt-get", "install", "-y"] + unique_packages
    elif shutil.which("yum"):
        cmd_update = ["yum", "makecache"]
        cmd_install = ["yum", "install", "-y"] + unique_packages
    else:
        print("⚠️ Предупреждение: Не найден поддерживаемый менеджер пакетов (APT/YUM). Пропускаем.")
        return

    try:
        # Для скорости можно закомментировать обновление кэша, если пакеты ставятся часто
        # subprocess.run(cmd_update, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        # Запускаем системную установку
        result = subprocess.run(cmd_install, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print("✅ Системные пакеты успешно установлены или уже есть в системе.")
        else:
            print(f"❌ Ошибка установки пакетов ОС:\n{result.stderr}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Критический сбой при вызове пакетного менеджера: {e}")
        sys.exit(1)

