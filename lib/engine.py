#!/usr/bin/env python3
"""
Amnezia Independent Deploy Engine.
Поддерживает кастомные пути (dest), права (mode), рекурсивный инклуд манифестов,
автовычисление {{ROOT_DIR}} (уровень выше манифеста) и создание символьных ссылок (symlinks).
"""

#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess
import deploy_config as config

# ИМПОРТ ВСЕХ НАШИХ МОДУЛЕЙ ПЛАГИНОВ
from lib.modules.sys_packages import install_system_dependencies
from lib.modules.env_manager import process_env_unit
from lib.modules.dependency_resolver import resolve_package_dependencies
from lib.modules.lifecycle_hooks import execute_lifecycle_hooks
from lib.modules.state_manager import register_package_install, execute_package_uninstall, load_state

class Engine:
    def __init__(self):
        self.units = {}        # filename -> {type, desc, base_dir, root_dir, dest, mode, src}
        self.packages = {}     # pkg_name -> {desc, include, requires, sys_packages, post_install, pre_uninstall}
        self.loaded_manifests = set()
        self.files_to_deploy = set()
        self.sys_packages_to_install = set()   # Стек системных пакетов ОС
        self.active_packages = set()           # Выбранные пакеты (для хуков)
        self.deployed_file_paths = []          # Сюда ловим все реальные dest-пути файлов для state.json
        self.active_package_context = "unknown" # Имя активного пакета для песочницы
        self.need_systemd_reload = False

    def check_root(self):
        if os.geteuid() != 0:
            print("❌ Ошибка: Запустите скрипт через sudo!")
            sys.exit(1)

    def load_manifest_recursive(self, manifest_path):
        abs_manifest_path = os.path.abspath(manifest_path)
        if abs_manifest_path in self.loaded_manifests:
            return
        self.loaded_manifests.add(abs_manifest_path)

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

        for relative_include in data.get("includes", []):
            include_path = os.path.normpath(os.path.join(base_dir, relative_include))
            self.load_manifest_recursive(include_path)

        for u_name, u_info in data.get("units", {}).items():
            u_info["base_dir"] = base_dir
            if "root_dir" in u_info:
                u_info["root_dir"] = os.path.normpath(os.path.join(base_dir, u_info["root_dir"]))
            else:
                u_info["root_dir"] = os.path.dirname(base_dir)
            self.units[u_name] = u_info

        for p_name, p_info in data.get("packages", {}).items():
            if p_name in self.packages:
                existing = self.packages[p_name].get("include", [])
                new_inc = p_info.get("include", [])
                self.packages[p_name]["include"] = list(set(existing + new_inc))
                self.packages[p_name]["requires"] = list(set(self.packages[p_name].get("requires", []) + p_info.get("requires", [])))
                self.packages[p_name]["sys_packages"] = list(set(self.packages[p_name].get("sys_packages", []) + p_info.get("sys_packages", [])))
                self.packages[p_name]["post_install"] = list(set(self.packages[p_name].get("post_install", []) + p_info.get("post_install", [])))
                self.packages[p_name]["pre_uninstall"] = list(set(self.packages[p_name].get("pre_uninstall", []) + p_info.get("pre_uninstall", [])))
            else:
                self.packages[p_name] = p_info

    def resolve_dependencies(self, item_name):
        if item_name in self.packages:
            self.active_packages.add(item_name)
        resolve_package_dependencies(self, item_name)

    def get_paths_and_modes(self, filename):
        file_info = self.units.get(filename, {})
        base_dir = file_info.get("base_dir", ".")
        file_type = file_info.get("type", "")

        sandbox_folder_name = f"{config.ENV_PREFIX}{self.active_package_context}"
        sandbox_dir = os.path.join(config.ENV_PATH, sandbox_folder_name)

        src = "NOT_FOUND"
        if file_type not in ["symlink", "env"]:
            lookup_paths = [
                os.path.join(base_dir, filename),
                os.path.join(base_dir, "scripts", filename),
                os.path.join(base_dir, "systemd", filename)
            ]
            for p in lookup_paths:
                if os.path.exists(p): src = p; break
        elif file_type == "env_file":
            if os.path.exists(os.path.join(base_dir, filename)): src = os.path.join(base_dir, filename)
        else:
            src = file_info.get("src", "")

        if "dest" in file_info:
            dest = file_info["dest"]
        elif file_type == "env":
            dest = os.path.join(sandbox_dir, "env")
        elif file_type == "env_file":
            dest = os.path.join(sandbox_dir, os.path.basename(filename))
        elif file_type in ["unit", "service", "timer"] or filename.endswith(('.service', '.timer')):
            dest = os.path.join(config.SYS_SYSTEMD, os.path.basename(filename))
        else:
            dest = os.path.join(config.SYS_BIN, os.path.basename(filename))

        if "mode" in file_info:
            mode = int(file_info["mode"], 8)
        elif file_type in ["env", "env_file"]:
            mode = 0o600
        elif file_type in ["unit", "service", "timer"] or filename.endswith(('.service', '.timer')):
            mode = 0o644
        elif file_type == "script" or filename.endswith(('.sh', '.py')):
            mode = 0o755
        else:
            mode = 0o644

        return src, dest, mode, file_type

    def install_files(self):
        # ЗАЩИТА: Проверяем, не установлен ли пакет уже, чтобы не затереть живой конфиг случайно
        current_state = load_state()
        for pkg in self.active_packages:
            if pkg in current_state.get("installed_packages", {}):
                print(f"⚠️ Предупреждение: Пакет '{pkg}' уже развернут в системе!")
                print(f"👉 Используйте команду 'reinstall' для чистой перезаписи.")
                return

        if self.sys_packages_to_install:
            install_system_dependencies(list(self.sys_packages_to_install))

        print("\n" + "="*50)
        print("🚀 ЗАПУСК ОРКЕСТРАЦИИ И ДЕПЛОЯ ФАЙЛОВ:")
        print("="*50)
        
        for fname in sorted(self.files_to_deploy):
            file_info = self.units.get(fname, {})
            base_dir = os.path.abspath(file_info.get("base_dir", "."))
            root_dir = os.path.abspath(file_info.get("root_dir", "."))
            
            src, dest, mode, f_type = self.get_paths_and_modes(fname)
            
            if f_type == "env":
                dest = process_env_unit(fname, file_info, dest)
                self.deployed_file_paths.append(dest) # Фиксируем сгенерированный .env в реестр
                continue

            context_vars = {
                "{{ROOT_DIR}}": root_dir,
                "{{BASE_DIR}}": base_dir,
                "{{SYS_BIN}}": config.SYS_BIN,
                "{{SYS_SYSTEMD}}": config.SYS_SYSTEMD
            }

            for marker, real_value in context_vars.items():
                if src != "NOT_FOUND": src = src.replace(marker, real_value)
                dest = dest.replace(marker, real_value)

            if src == "NOT_FOUND":
                print(f"❌ Ошибка: Файл {fname} физически отсутствует на диске!")
                sys.exit(1)

            # Фиксируем целевой путь файла (или симлинка) для истории в state.json
            self.deployed_file_paths.append(dest)

            if f_type == "symlink":
                print(f" 🔗 Создание символьной ссылки: {dest} -> {src}")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if os.path.exists(dest) or os.path.islink(dest): os.remove(dest)
                os.symlink(src, dest)
                continue

            print(f" -> Обработка и копирование: {fname} ==> {dest}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)

            try:
                with open(src, "r", encoding="utf-8") as f_src:
                    content = f_src.read()
                for marker, real_value in context_vars.items():
                    content = content.replace(marker, real_value)
                with open(dest, "w", encoding="utf-8") as f_dest:
                    f_dest.write(content)
            except UnicodeDecodeError:
                shutil.copy2(src, dest)

            os.chown(dest, 0, 0)
            os.chmod(dest, mode)
            
            if f_type in ["unit", "service", "timer"] or dest.startswith(config.SYS_SYSTEMD):
                subprocess.run(["systemctl", "enable", fname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.need_systemd_reload = True
                
        if self.need_systemd_reload:
            print("\n🔄 Перезагрузка демона systemd (daemon-reload)...")
            subprocess.run(["systemctl", "daemon-reload"])

        if self.active_packages:
            execute_lifecycle_hooks("post_install", list(self.active_packages), self)

        # ФИНАЛ: Записываем успешную установку всех файлов пакета в state.json
        for pkg in self.active_packages:
            register_package_install(pkg, self.deployed_file_paths)

        print("\n🎉 Процесс развертывания успешно завершен!")

    def uninstall_package(self, pkg_name):
        """Метод полной деинсталляции пакета"""
        self.check_root()
        # 1. Запускаем пре-унисталл хуки из манифеста, пока файлы еще живы
        if pkg_name in self.packages:
            execute_lifecycle_hooks("pre_uninstall", [pkg_name], self)
        # 2. Вызываем системную зачистку файлов и systemd через state_manager
        return execute_package_uninstall(pkg_name, self)

