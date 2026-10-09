#!/usr/bin/env python3
"""
Модуль рекурсивной загрузки и парсинга JSON-манифестов инфраструктуры.
"""
import os
import sys
import json

def load_manifest_recursive(engine, manifest_path, parent_package_names=None):
    """
    Рекурсивно считывает manifest.json, парсит блоки includes, units и packages,
    автоматически изолируя имена вложенных юнитов и сохраняя иерархию пакетов для TUI.
    """
    abs_manifest_path = os.path.abspath(manifest_path)
    if abs_manifest_path in engine.loaded_manifests:
        return
    engine.loaded_manifests.add(abs_manifest_path)

    if not os.path.exists(abs_manifest_path):
        print(f"❌ Ошибка: Манифест не найден: {abs_manifest_path}")
        sys.exit(1)

    base_dir = os.path.dirname(abs_manifest_path)

    try:
        with open(abs_manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения JSON в {abs_manifest_path}: {e}")
        sys.exit(1)

    # Динамически вычисляем префикс пространства имён
    is_root = len(engine.loaded_manifests) == 1
    prefix = "" if is_root else f"{os.path.basename(base_dir)}:"

    # Собираем имена пакетов, объявленных именно В ЭТОМ файле манифеста
    current_manifest_packages = list(data.get("packages", {}).keys())

    # Если этот манифест был вызван из родительского, связываем их в иерархию
    if parent_package_names and current_manifest_packages:
        for p_parent in parent_package_names:
            if p_parent in engine.packages:
                if "sub_packages" not in engine.packages[p_parent]:
                    engine.packages[p_parent]["sub_packages"] = []
                for p_child in current_manifest_packages:
                    if p_child not in engine.packages[p_parent]["sub_packages"]:
                        engine.packages[p_parent]["sub_packages"].append(p_child)

    # 1. Рекурсивно обрабатываем цепочки вложенных манифестов (includes)
    # Передаем имена текущих пакетов как родительские для следующего уровня вложенности
    for relative_include in data.get("includes", []):
        include_path = os.path.normpath(os.path.join(base_dir, relative_include))
        load_manifest_recursive(engine, include_path, parent_package_names=current_manifest_packages)

    # 2. Парсим и регистрируем атомарные юниты с учетом пространства имён
    for u_name, u_info in data.get("units", {}).items():
        u_info["base_dir"] = base_dir
        if "root_dir" in u_info:
            u_info["root_dir"] = os.path.normpath(os.path.join(base_dir, u_info["root_dir"]))
        else:
            u_info["root_dir"] = os.path.dirname(base_dir)
            
        namespaced_u_name = f"{prefix}{u_name}" if prefix and not u_name.startswith(prefix) else u_name
        engine.units[namespaced_u_name] = u_info

    # 3. Парсим и объединяем пакеты, адаптируя имена включенных юнитов
    for p_name, p_info in data.get("packages", {}).items():
        if "include" in p_info:
            p_info["include"] = [
                f"{prefix}{item}" if prefix and not item.startswith(prefix) else item 
                for item in p_info["include"]
            ]

        if p_name in engine.packages:
            engine.packages[p_name]["include"] = list(set(engine.packages[p_name].get("include", []) + p_info.get("include", [])))
            engine.packages[p_name]["requires"] = list(set(engine.packages[p_name].get("requires", []) + p_info.get("requires", [])))
            engine.packages[p_name]["sys_packages"] = list(set(engine.packages[p_name].get("sys_packages", []) + p_info.get("sys_packages", [])))
            engine.packages[p_name]["post_install"] = list(set(engine.packages[p_name].get("post_install", []) + p_info.get("post_install", [])))
            engine.packages[p_name]["pre_uninstall"] = list(set(engine.packages[p_name].get("pre_uninstall", []) + p_info.get("pre_uninstall", [])))
        else:
            p_info["is_sub_package"] = not is_root  # Помечаем, является ли пакет вложенным
            engine.packages[p_name] = p_info

