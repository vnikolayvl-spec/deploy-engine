#!/usr/bin/env python3
"""
Модуль расчета целевых путей, масок прав доступа и сканирования конвенции папок files/.
"""
import os
import deploy_config as config

def get_paths_and_modes(engine, filename):
    """
    Вычисляет исходный путь (src), целевой путь установки (dest),
    права доступа (mode) и тип атомарного юнита на основе конвенций.
    """
    file_info = engine.units.get(filename, {})
    base_dir = file_info.get("base_dir", ".")
    file_type = file_info.get("type", "file")  # По умолчанию тип универсальный - file

    # Каталог песочницы секретов из глобального deploy_config
    sandbox_dir = os.path.join(config.ENV_PATH, f"{config.ENV_PREFIX}{engine.active_package_context}")

    src = "NOT_FOUND"
    if file_type not in ["symlink", "env"]:
        # Добавляем подпапку "files" в цепочку автоматического поиска ресурсов репозитория!
        lookup_paths = [
            os.path.join(base_dir, filename),
            os.path.join(base_dir, "files", filename),
            os.path.join(base_dir, "scripts", filename),
            os.path.join(base_dir, "systemd", filename)
        ]
        for p in lookup_paths:
            if os.path.exists(p):
                src = p
                break
    else:
        src = file_info.get("src", "")

    # 1. Интеллектуальный расчет целевых путей назначения (dest)
    if "dest" in file_info:
        dest = file_info["dest"]
    elif file_type == "env":
        # Имя файла окружения берем оригинальное из JSON или дефолтное "env"
        dest = os.path.join(sandbox_dir, os.path.basename(filename) if "." in filename else "env")
    elif file_type in ["unit", "service", "timer"] or filename.endswith(('.service', '.timer')):
        dest = os.path.join(config.SYS_SYSTEMD, os.path.basename(filename))
    elif file_type == "script" or filename.endswith(('.sh', '.py')):
        dest = os.path.join(config.SYS_BIN, os.path.basename(filename))
    else:
        # ТИП FILE: по умолчанию зеркально летит в /etc/de_{имя_пакета}/files/[имя_файла]
        dest = os.path.join("/etc", f"de_{engine.active_package_context}", "files", filename)

    # 2. Вычисление прав доступа по умолчанию (mode)
    if "mode" in file_info:
        mode = int(file_info["mode"], 8)
    elif file_type == "env":
        mode = 0o600  # Секреты всегда намертво закрыты маской 600
    elif file_type in ["unit", "service", "timer"] or filename.endswith(('.service', '.timer')):
        mode = 0o644
    elif file_type == "script" or filename.endswith(('.sh', '.py')):
        mode = 0o755
    else:
        mode = 0o644

    return src, dest, mode, file_type

