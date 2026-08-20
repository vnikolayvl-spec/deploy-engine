#!/usr/bin/env python3
"""
Модуль выполнения хуков жизненного цикла (post_install / pre_uninstall).
"""
import subprocess
import sys

def execute_lifecycle_hooks(hook_type, packages_list, engine):
    """
    Пробегает по списку выбранных пакетов, собирает команды из указанного hook_type 
    (например, 'post_install'), шаблонизирует их и запускает в системе.
    """
    # Собираем все хуки по порядку для каждого активного пакета
    for pkg_name in sorted(packages_list):
        if pkg_name not in engine.packages:
            continue
            
        pkg_info = engine.packages[pkg_name]
        hooks = pkg_info.get(hook_type, [])
        if not hooks:
            continue

        print("\n" + "-"*50)
        print(f"🎬 [ХУК] Выполнение {hook_type} для пакета: {pkg_name.upper()}")
        print("-"*50)

        # Вычисляем контекст путей для конкретного пакета (берем из его первого юнита или дефолт)
        base_dir = "."
        root_dir = "."
        for fname in pkg_info.get("include", []):
            if fname in engine.units:
                base_dir = engine.units[fname].get("base_dir", ".")
                root_dir = engine.units[fname].get("root_dir", ".")
                break

        import deploy_config as config
        context_vars = {
            "{{ROOT_DIR}}": root_dir,
            "{{BASE_DIR}}": base_dir,
            "{{SYS_BIN}}": config.SYS_BIN,
            "{{SYS_SYSTEMD}}": config.SYS_SYSTEMD
        }

        # Выполняем каждую команду по очереди
        for cmd_template in hooks:
            cmd = cmd_template
            for marker, real_value in context_vars.items():
                cmd = cmd.replace(marker, real_value)

            print(f" -> Запуск команды: {cmd}")
            try:
                # Запускаем команду в шелле, перенаправляя вывод для красивого отображения в консоли
                result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
                
                if result.stdout:
                    print(f"   [STDOUT]:\n{result.stdout.strip()}")
                if result.stderr:
                    print(f"   [STDERR]:\n{result.stderr.strip()}")
                    
                if result.returncode != 0:
                    print(f"❌ Ошибка: Команда завершилась с кодом {result.returncode}. Остановка деплоя.")
                    sys.exit(1)
            except Exception as e:
                print(f"❌ Критический сбой при выполнении хука: {e}")
                sys.exit(1)

