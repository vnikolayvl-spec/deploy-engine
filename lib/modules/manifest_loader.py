#!/usr/bin/env python3
"""
Модуль рекурсивной загрузки и парсинга JSON-манифестов инфраструктуры.
"""
import os
import sys
import json

def load_manifest_recursive(engine, manifest_path):
    """
    Рекурсивно считывает manifest.json, парсит блоки includes, units и packages,
    а затем наполняет плоские словари конфигурации инстанса Engine.
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

    # 1. Рекурсивно обрабатываем цепочки вложенных манифестов (includes)
    for relative_include in data.get("includes", []):
        include_path = os.path.normpath(os.path.join(base_dir, relative_include))
        load_manifest_recursive(engine, include_path)

    # 2. Парсим и регистрируем атомарные юниты (компоненты/файлы)
    for u_name, u_info in data.get("units", {}).items():
        u_info["base_dir"] = base_dir
        # Вычисляем root_dir: если прописан кастомный в JSON — берем его, иначе шаг на уровень выше
        if "root_dir" in u_info:
            u_info["root_dir"] = os.path.normpath(os.path.join(base_dir, u_info["root_dir"]))
        else:
            u_info["root_dir"] = os.path.dirname(base_dir)
        engine.units[u_name] = u_info

    # 3. Парсим и объединяем пакеты (комплексные IaC сценарии)
    for p_name, p_info in data.get("packages", {}).items():
        if p_name in engine.packages:
            # Если имя пакета совпадает в разных манифестах — склеиваем их массивы ресурсов без дублирования
            engine.packages[p_name]["include"] = list(set(engine.packages[p_name].get("include", []) + p_info.get("include", [])))
            engine.packages[p_name]["requires"] = list(set(engine.packages[p_name].get("requires", []) + p_info.get("requires", [])))
            engine.packages[p_name]["sys_packages"] = list(set(engine.packages[p_name].get("sys_packages", []) + p_info.get("sys_packages", [])))
            engine.packages[p_name]["post_install"] = list(set(engine.packages[p_name].get("post_install", []) + p_info.get("post_install", [])))
            engine.packages[p_name]["pre_uninstall"] = list(set(engine.packages[p_name].get("pre_uninstall", []) + p_info.get("pre_uninstall", [])))
        else:
            engine.packages[p_name] = p_info

