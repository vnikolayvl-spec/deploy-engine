#!/usr/bin/env python3
"""
Модуль рекурсивного раскрытия зависимостей пакетов и файлов.
"""

def resolve_package_dependencies(engine, item_name):
    """
    Рекурсивно собирает уникальные файлы, внутренние requires и sys_packages ОС,
    наполняя соответствующие сеты (set) переданного инстанса Engine.
    """
    if item_name in engine.units:
        engine.files_to_deploy.add(item_name)
        return
        
    if item_name in engine.packages:
        pkg_info = engine.packages[item_name]
        
        # Запоминаем имя самого родительского (высокоуровневого) пакета для контекста песочницы
        if engine.active_package_context == "unknown":
            engine.active_package_context = item_name
            
        # 1. Сначала собираем системные пакеты ОС (Apt/Yum)
        for sys_pkg in pkg_info.get("sys_packages", []):
            engine.sys_packages_to_install.add(sys_pkg)
            
        # 2. Рекурсивно раскрываем внутренние зависимости (requires) от других пакетов
        for req_pkg in pkg_info.get("requires", []):
            resolve_package_dependencies(engine, req_pkg)
            
        # 3. Собираем файлы и юниты, входящие в этот пакет
        for child in pkg_info.get("include", []):
            resolve_package_dependencies(engine, child)
        return
        
    print(f"⚠️ Предупреждение: Компонент '{item_name}' не найден в манифестах!")

