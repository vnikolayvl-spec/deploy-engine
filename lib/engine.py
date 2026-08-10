#!/usr/bin/env python3
"""
Amnezia Independent Deploy Engine.
Поддерживает кастомные пути (dest), права (mode), рекурсивный инклуд манифестов,
автовычисление {{ROOT_DIR}} (уровень выше манифеста) и создание символьных ссылок (symlinks).
"""
import os
import sys
import json
import shutil
import subprocess
import deploy_config as config

class Engine:
    def __init__(self):
        self.units = {}        # filename -> {type, desc, base_dir, root_dir, dest, mode, src}
        self.packages = {}     # pkg_name -> {desc, include}
        self.loaded_manifests = set()
        self.files_to_deploy = set()
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
        # АВТОВЫЧИСЛЕНИЕ ROOT_DIR: корень проекта — это всегда папка на уровень выше папки манифеста
        root_dir = os.path.dirname(base_dir)

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
            
            # Проверяем, указал ли пользователь кастомный корень (например, "..")
            if "root_dir" in u_info:
                # Вычисляем путь относительно папки текущего манифеста
                custom_root = os.path.join(base_dir, u_info["root_dir"])
                u_info["root_dir"] = os.path.normpath(custom_root)
            else:
                # Если поля нет — оставляем стандартное автовычисление (уровень выше манифеста)
                u_info["root_dir"] = os.path.dirname(base_dir)
                
            self.units[u_name] = u_info

        for p_name, p_info in data.get("packages", {}).items():
            if p_name in self.packages:
                existing = self.packages[p_name].get("include", [])
                new_inc = p_info.get("include", [])
                self.packages[p_name]["include"] = list(set(existing + new_inc))
            else:
                self.packages[p_name] = p_info

    def resolve_dependencies(self, item_name):
        if item_name in self.units:
            self.files_to_deploy.add(item_name)
            return
        if item_name in self.packages:
            for child in self.packages[item_name].get("include", []):
                self.resolve_dependencies(child)
            return
        print(f"⚠️ Предупреждение: Компонент '{item_name}' не найден в манифестах!")

    def get_paths_and_modes(self, filename):
        """Вычисляет исходный путь, целевой путь, права доступа и тип атомарно"""
        file_info = self.units.get(filename, {})
        base_dir = file_info.get("base_dir", ".")
        file_type = file_info.get("type", "")

        # 1. Поиск исходника в репозитории (для файлов копирования)
        src = "NOT_FOUND"
        if file_type != "symlink":
            lookup_paths = [
                os.path.join(base_dir, filename),
                os.path.join(base_dir, "scripts", filename),
                os.path.join(base_dir, "systemd", filename)
            ]
            for p in lookup_paths:
                if os.path.exists(p):
                    src = p
                    break
        else:
            # Для симлинков исходным путем является то, что прописано в поле "src" в JSON
            src = file_info.get("src", "")

        # 2. Вычисление целевого пути (dest)
        if "dest" in file_info:
            dest = file_info["dest"]
        elif file_type in ["unit", "service", "timer"] or filename.endswith(('.service', '.timer')):
            # os.path.basename отсечет "amnezia-stat/" и оставит только чистое имя файла
            dest = os.path.join(config.SYS_SYSTEMD, os.path.basename(filename))
        else:
            dest = os.path.join(config.SYS_BIN, os.path.basename(filename))


        # 3. Вычисление прав доступа (mode)
        if "mode" in file_info:
            mode = int(file_info["mode"], 8)
        elif file_type in ["unit", "service", "timer"] or filename.endswith(('.service', '.timer')):
            mode = 0o644
        elif file_type == "script" or filename.endswith('.sh') or filename.endswith('.py'):
            mode = 0o755
        else:
            mode = 0o644

        return src, dest, mode, file_type

    def install_files(self):
        print("\n" + "="*50)
        print("🚀 ЗАПУСК ОРКЕСТРАЦИИ И УСТАНОВКИ:")
        print("="*50)
        
        for fname in sorted(self.files_to_deploy):
            file_info = self.units.get(fname, {})
            base_dir = os.path.abspath(file_info.get("base_dir", "."))
            root_dir = os.path.abspath(file_info.get("root_dir", "."))
            
            src, dest, mode, f_type = self.get_paths_and_modes(fname)
            
            # Словарь контекстных переменных для динамической шаблонизации путей
            context_vars = {
                "{{ROOT_DIR}}": root_dir,
                "{{BASE_DIR}}": base_dir,
                "{{SYS_BIN}}": config.SYS_BIN,
                "{{SYS_SYSTEMD}}": config.SYS_SYSTEMD
            }

            # Прогоняем пути через шаблонизатор (это критично для кастомных полей dest и src симлинков)
            for marker, real_value in context_vars.items():
                if src != "NOT_FOUND":
                    src = src.replace(marker, real_value)
                dest = dest.replace(marker, real_value)

            if src == "NOT_FOUND":
                print(f"❌ Ошибка: Файл {fname} физически отсутствует на диске!")
                sys.exit(1)

            # --- ОБРАБОТКА ТИПА SYMLINK ---
            if f_type == "symlink":
                print(f" 🔗 Создание символьной ссылки: {dest} -> {src}")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                
                # Если симлинк или файл по этому пути уже существует, принудительно удаляем его, чтобы избежать ошибок
                if os.path.exists(dest) or os.path.islink(dest):
                    os.remove(dest)
                
                os.symlink(src, dest)
                continue # Переходим к следующему элементу, права и chown для ссылок не настраиваются

            # --- ОБРАБОТКА ОБЫЧНЫХ ФАЙЛОВ С ШАБЛОНИЗАЦИЕЙ ВНУТРИ КОДА ---
            print(f" -> Копирование и шаблонизация: {fname} ==> {dest}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)

            try:
                # Пробуем прочитать файл как текстовый шаблон для подстановки {{ROOT_DIR}} внутрь кода Python/Bash
                with open(src, "r", encoding="utf-8") as f_src:
                    content = f_src.read()
                
                for marker, real_value in context_vars.items():
                    content = content.replace(marker, real_value)
                
                with open(dest, "w", encoding="utf-8") as f_dest:
                    f_dest.write(content)
                    
            except UnicodeDecodeError:
                # Если файл бинарный — просто копируем по-честному
                shutil.copy2(src, dest)

            # Выставляем владельца root:root и права доступа
            os.chown(dest, 0, 0)
            os.chmod(dest, mode)
            
            if f_type in ["unit", "service", "timer"] or dest.startswith(config.SYS_SYSTEMD):
                subprocess.run(["systemctl", "enable", fname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.need_systemd_reload = True
                
        if self.need_systemd_reload:
            print("\n🔄 Перезагрузка демона systemd (daemon-reload)...")
            subprocess.run(["systemctl", "daemon-reload"])
        print("\n🎉 Все компоненты и символьные ссылки успешно развернуты!")
