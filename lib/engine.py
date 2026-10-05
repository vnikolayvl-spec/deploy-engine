#!/usr/bin/env python3
"""
Amnezia Independent Deploy Engine.
Главное ядро оркестрации (Стейт-Хаб). Хранит структуры данных
и делегирует выполнение изолированным плагинам-модулям.
"""
import os
import sys

# Импортируем все наши атомарные плагины модулей
from lib.modules.manifest_loader import load_manifest_recursive
from lib.modules.path_resolver import get_paths_and_modes
from lib.modules.dependency_resolver import resolve_package_dependencies
from lib.modules.file_installer import run_deployment_pipeline
from lib.modules.lifecycle_hooks import execute_lifecycle_hooks
from lib.modules.state_manager import register_package_install, execute_package_uninstall

class Engine:
    def __init__(self):
        self.units = {}        # filename -> {type, desc, base_dir, root_dir, dest, mode, src}
        self.packages = {}     # pkg_name -> {desc, include, requires, sys_packages, post_install, pre_uninstall}
        self.loaded_manifests = set()
        self.files_to_deploy = set()
        self.sys_packages_to_install = set()   # Стек системных пакетов ОС
        self.active_packages = set()           # Сет выбранных пакетов (для хуков)
        self.deployed_files_map = {}           # Карта метаданных: реальный_dest -> f_type (для pack.env)
        self.active_package_context = "unknown" # Имя активного пакета для песочницы
        self.need_systemd_reload = False

    def check_root(self):
        if os.geteuid() != 0:
            print("❌ Ошибка: Запустите скрипт через sudo!")
            sys.exit(1)

    def load_manifest_recursive(self, manifest_path):
        """Делегирует загрузку манифестов и автовычисление {{ROOT_DIR}} плагину"""
        load_manifest_recursive(self, manifest_path)

    def resolve_dependencies(self, item_name):
        """Делегирует рекурсивный сбор дерева зависимостей плагину"""
        if item_name in self.packages:
            self.active_packages.add(item_name)
        resolve_package_dependencies(self, item_name)

    def get_paths_and_modes(self, filename):
        """Делегирует расчет конвенций путей и сканирование files/ плагину"""
        return get_paths_and_modes(self, filename)

    def install_files(self):
        """Управляет сквозным конвейером установки через цепочку вызовов модулей"""
        # 1. Запуск конвейера физической установки и шаблонизации файлов
        run_deployment_pipeline(self)

        # 2. Выполнение пост-инсталл хуков (post_install) силами модуля hooks
        if self.active_packages:
            execute_lifecycle_hooks("post_install", list(self.active_packages), self)

        # 3. Финал: Передаем метаданные в state_manager для сборки реестра и паспортов pack.env
        for pkg in self.active_packages:
            register_package_install(pkg, self.deployed_files_map)

        print("\n🎉 Процесс развертывания успешно завершен!")

    def uninstall_package(self, pkg_name):
        """Метод полной деинсталляции пакета"""
        self.check_root()
        # Вызываем пре-унисталл хуки из манифеста, пока файлы еще живы
        if pkg_name in self.packages:
            execute_lifecycle_hooks("pre_uninstall", [pkg_name], self)
        # Вызываем системную зачистку файлов и песочниц через state_manager
        return execute_package_uninstall(pkg_name, self)

