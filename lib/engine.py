#!/usr/bin/env python3
import os
import sys
import json
import shutil
import subprocess
import deploy_config as config

class Engine:
    def __init__(self):
        self.units = {}        # filename -> {type, desc, base_dir, dest, mode}
        self.packages = {}     # pkg_name -> {desc, include}
        self.loaded_manifests = set()
        self.files_to_deploy = set()
        self.need_systemd_reload = False

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
        file_info = self.units.get(filename, {})
        base_dir = file_info.get("base_dir", ".")
        file_type = file_info.get("type", "")

        lookup_paths = [
            os.path.join(base_dir, filename),
            os.path.join(base_dir, "scripts", filename),
            os.path.join(base_dir, "systemd", filename)
        ]
        src = "NOT_FOUND"
        for p in lookup_paths:
            if os.path.exists(p):
                src = p
                break

        if "dest" in file_info:
            dest = file_info["dest"]
        elif file_type in ["unit", "service", "timer"] or filename.endswith(('.service', '.timer')):
            dest = os.path.join(config.SYS_SYSTEMD, filename)
        else:
            dest = os.path.join(config.SYS_BIN, filename)

        if "mode" in file_info:
            mode = int(file_info["mode"], 8)
        elif file_type in ["unit", "service", "timer"] or filename.endswith(('.service', '.timer')):
            mode = 0o644
        elif file_type == "script" or filename.endswith('.sh'):
            mode = 0o755
        else:
            mode = 0o644

        return src, dest, mode, file_type

    def install_files(self):
        print("\n" + "="*50)
        print("🚀 ЗАПУСК ФИЗИЧЕСКОЙ УСТАНОВКИ:")
        print("="*50)
        
        for fname in sorted(self.files_to_deploy):
            src, dest, mode, f_type = self.get_paths_and_modes(fname)
            if src == "NOT_FOUND":
                print(f"❌ Ошибка: Файл {fname} физически отсутствует на диске!")
                sys.exit(1)
                
            print(f" -> Установка: {fname} ==> {dest} (mode: {oct(mode)[2:]})")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            os.chown(dest, 0, 0)
            os.chmod(dest, mode)
            
            if f_type in ["unit", "service", "timer"] or dest.startswith(config.SYS_SYSTEMD):
                subprocess.run(["systemctl", "enable", fname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.need_systemd_reload = True
                
        if self.need_systemd_reload:
            print("\n🔄 Перезагрузка демона systemd (daemon-reload)...")
            subprocess.run(["systemctl", "daemon-reload"])
        print("\n🎉 Все выбранные компоненты успешно развернуты!")
