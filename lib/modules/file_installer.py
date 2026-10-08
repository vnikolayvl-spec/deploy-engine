#!/usr/bin/env python3
"""
Модуль физической установки файлов, создания символьных ссылок и шаблонизации кода.
"""
import os
import sys
import stat
import shutil
import subprocess
import deploy_config as config

# Импортируем менеджеры системных пакетов и секретов, так как они вызываются внутри пайплайна
from lib.modules.sys_packages import install_system_dependencies
from lib.modules.env_manager import process_env_unit
from lib.modules.state_manager import register_package_install, load_state

def run_deployment_pipeline(engine):
    """
    Основной конвейер физической оркестрации. Выполняет установку системного софта,
    компиляцию .env файлов, копирование статики/скриптов и генерацию паспортов pack.env.
    """
    # 1. ЗАЩИТА: Блокируем случайную перезапись живой системы без команды reinstall
    current_state = load_state()
    for pkg in engine.active_packages:
        if pkg in current_state.get("installed_packages", {}):
            print(f"⚠️ Предупреждение: Пакет '{pkg}' уже развернут в системе!")
            print(f"👉 Используйте команду 'reinstall' для чистой перезаписи.")
            return

    # 2. ЭТАП 1: Установка системных APT/YUM зависимостей
    if engine.sys_packages_to_install:
        install_system_dependencies(list(engine.sys_packages_to_install))

    print("\n" + "="*50)
    print("🚀 ЗАПУСК ОРКЕСТРАЦИИ И ДЕПЛОЯ ФАЙЛОВ:")
    print("="*50)
    
    # 3. ЭТАП 2: Перебираем и разворачиваем все выбранные юниты
    for fname in sorted(engine.files_to_deploy):
        file_info = engine.units.get(fname, {})
        base_dir = os.path.abspath(file_info.get("base_dir", "."))
        root_dir = os.path.abspath(file_info.get("root_dir", "."))

        src, dest, mode, f_type = engine.get_paths_and_modes(fname)

        # Если движок вернул пустой src или относительный путь, 
        # привязываем его к базовой директории манифеста (base_dir)
        if not src or src == "NOT_FOUND":
            potential_src = os.path.join(base_dir, fname)
            if os.path.exists(potential_src):
                src = potential_src

        
        # Сборка словаря контекстных переменных
        context_vars = {
            "{{ROOT_DIR}}": root_dir,
            "{{BASE_DIR}}": base_dir,
            "{{SYS_BIN}}": config.SYS_BIN,
            "{{SYS_SYSTEMD}}": config.SYS_SYSTEMD
        }

        # Шаблонизируем системные пути установки (src и dest)
        for marker, real_value in context_vars.items():
            if src != "NOT_FOUND": 
                src = src.replace(marker, real_value)
            dest = dest.replace(marker, real_value)

        # Обработка динамических настроек типа env (Промпты, Upsert-слияние)
        if f_type == "env":
            dest = process_env_unit(fname, file_info, src, dest)
            engine.deployed_files_map[dest] = "env"
            continue

        if src == "NOT_FOUND":
            print(f"❌ Ошибка: Файл {fname} физически отсутствует на диске!")
            sys.exit(1)

        # Фиксируем итоговый путь файла в словаре метаданных для паспорта pack.env
        engine.deployed_files_map[dest] = f_type

        # Создание символьных ссылок (symlink)
        if f_type == "symlink":
            print(f" 🔗 Создание символьной ссылки: {dest} -> {src}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.exists(dest) or os.path.islink(dest): 
                os.remove(dest)
            os.symlink(src, dest)
            continue

        # Копирование и шаблонизация текстовых файлов
        # Разделение логики: Копирование целой директории VS атомарный файл
        if os.path.isdir(src):
            print(f" 📂 Рекурсивное копирование директории: {fname} ==> {dest}")
            if os.path.exists(dest):
                if os.path.islink(dest):
                    os.remove(dest)
                else:
                    shutil.rmtree(dest)
            # Фильтруем сокеты и специальные файлы, чтобы shutil не падал при копировании
            def ignore_special_files(dir_path, list_of_names):
                ignored = []
                for name in list_of_names:
                    full_path = os.path.join(dir_path, name)
                    try:
                        # Получаем битовую маску свойств файла без перехода по симлинкам
                        mode = os.lstat(full_path).st_mode
                        # Проверяем, сокет ли это или FIFO канал
                        if stat.S_ISSOCK(mode) or stat.S_ISFIFO(mode):
                            ignored.append(name)
                    except OSError:
                        # Если файл исчез в процессе или недоступен, пропускаем
                        pass
                return ignored

            shutil.copytree(src, dest, symlinks=True, ignore=ignore_special_files)

        else:
            print(f" -> Обработка и копирование файла: {fname} ==> {dest}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)

            try:
                with open(src, "r", encoding="utf-8") as f_src:
                    content = f_src.read()
                for marker, real_value in context_vars.items():
                    content = content.replace(marker, real_value)
                with open(dest, "w", encoding="utf-8") as f_dest:
                    f_dest.write(content)
            except UnicodeDecodeError:
                # Если файл бинарный — копируем напрямую без декодирования строки
                shutil.copy2(src, dest)


        # Выставляем владельца root:root и права доступа
        os.chown(dest, 0, 0)
        os.chmod(dest, mode)
        
        # Регистрация служб в автозагрузку ОС Linux
        if f_type in ["unit", "service", "timer"] or dest.startswith(config.SYS_SYSTEMD):
            subprocess.run(["systemctl", "enable", fname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            engine.need_systemd_reload = True
            
    if engine.need_systemd_reload:
        print("\n🔄 Перезагрузка демона systemd (daemon-reload)...")
        subprocess.run(["systemctl", "daemon-reload"])

