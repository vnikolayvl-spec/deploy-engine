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
        clean_filename = filename.split(":")[-1]
        lookup_paths = [
            os.path.join(base_dir, clean_filename),
            os.path.join(base_dir, "files", clean_filename),
            os.path.join(base_dir, "scripts", clean_filename),
            os.path.join(base_dir, "systemd", clean_filename)
        ]
        for p in lookup_paths:
            if os.path.exists(p):
                src = p
                break
    else:
        src = file_info.get("src", "")

    # 1. Интеллектуальный расчет целевых путей назначения (dest)
    # Выделяем чистое имя файла без префиксов пространства имен (двоеточий) для работы с ФС
    clean_filename = filename.split(":")[-1]

    if "dest" in file_info:
        dest = file_info["dest"]
        # Раскрываем макросы «на лету» для корректного рендеринга плана в TUI
        root_dir = os.path.abspath(file_info.get("root_dir", "."))
        dest = dest.replace("{{ROOT_DIR}}", root_dir)
        dest = dest.replace("{{BASE_DIR}}", base_dir)
        dest = dest.replace("{{SYS_BIN}}", config.SYS_BIN)
        dest = dest.replace("{{SYS_SYSTEMD}}", config.SYS_SYSTEMD)
    elif file_type == "env":
        dest = os.path.join(sandbox_dir, os.path.basename(clean_filename) if "." in clean_filename else "env")
    elif file_type in ["unit", "service", "timer"] or clean_filename.endswith(('.service', '.timer')):
        dest = os.path.join(config.SYS_SYSTEMD, os.path.basename(clean_filename))
    elif file_type == "script" or clean_filename.endswith(('.sh', '.py')):
        dest = os.path.join(config.SYS_BIN, os.path.basename(clean_filename))
    else:
        # ТИП FILE: если чистое имя юнита 'files', то целевой путь — сам корень папки приложения
        base_files_dir = os.path.join("/opt", f"de_{engine.active_package_context}", "files")
        dest = base_files_dir if clean_filename == "files" else os.path.join(base_files_dir, clean_filename)

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

