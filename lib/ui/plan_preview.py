#!/usr/bin/env python3
"""
Кастомный виджет RichLog для красивого форматирования и рендеринга Сводного Плана на лету.
"""
import os
from textual.widgets import RichLog

class PlanPreviewLog(RichLog):
    def __init__(self, engine, app_instance, **kwargs):
        super().__init__(**kwargs)
        self.engine = engine
        self.app_ref = app_instance  # Ссылка на главное приложение для чтения self.actions

    def update_plan_view(self) -> None:
        """Перерасчитывает зависимости бэкенда и рендерит лог операций заново"""
        self.clear()
        
        plans = {"install": set(), "reinstall": set(), "uninstall": set()}
        for k, v in self.app_ref.actions.items():
            if v in plans: 
                plans[v].add(k)
            
        if not plans["install"] and not plans["reinstall"] and not plans["uninstall"]:
            self.write("[yellow]Используйте ПРОБЕЛ на пакетах для планирования операций...[/yellow]")
            return

        import deploy_config as config
        
        # Секция 1: Удаление пакетов [-]
        if plans["uninstall"]:
            self.write("[bold red]🚨 ПЛАН УДАЛЕНИЯ ПАКЕТОВ (ЭТАП 1):[/bold red]")
            for pkg in sorted(plans["uninstall"]):
                self.write(f"  [-] Пакет [bold]{pkg}[/bold] будет полностью стерт из системы")

        # Секция 2 и 3: Переустановка [↻] и Новая установка [+]
        for mode in ["reinstall", "install"]:
            if not plans[mode]: 
                continue
            title = "🔄 ПЛАН ПОЛНОЙ ПЕРЕУСТАНОВКИ (ЭТАП 2):" if mode == "reinstall" else "🎁 ПЛАН УСТАНОВКИ НОВЫХ ПАКЕТОВ (ЭТАП 3):"
            color = "yellow" if mode == "reinstall" else "green"
            
            self.write(f"\n[bold {color}]{title}[/bold {color}]")
            
            # Временно наполняем стек файлов движка для просчета путей этой группы
            self.engine.files_to_deploy.clear()
            for pkg in sorted(plans[mode]):
                try:
                    if hasattr(self.engine, "registry") and self.engine.registry.has(pkg):
                        self.engine.resolve_dependencies(pkg)
                    elif pkg in getattr(self.engine, "packages", {}):
                        self.engine.resolve_dependencies(pkg)
                except Exception as err:
                    self.write(f"  ⚠️ [red]Ошибка зависимостей для {pkg}: {err}[/red]")
                
            for fname in sorted(self.engine.files_to_deploy):
                pkg_name, unit_name = fname.split(":", 1) if ":" in fname else ("", fname)
                pkg = self.engine.registry.get(pkg_name) if pkg_name and hasattr(self.engine, "registry") and self.engine.registry.has(pkg_name) else {}
                file_info = pkg.get("units", {}).get(unit_name, {}) if pkg else self.engine.units.get(unit_name, {})
                base_dir = os.path.abspath(pkg.get("base_dir", ".")) if pkg else os.path.abspath(file_info.get("base_dir", "."))
                root_dir = os.path.abspath(pkg.get("root_dir", base_dir)) if pkg else os.path.abspath(file_info.get("root_dir", "."))
                
                src, dest, mode_mask, f_type = self.engine.get_paths_and_modes(fname)
                desc = file_info.get("desc") or file_info.get("description", "")
                
                context_vars = {
                    "{{ROOT_DIR}}": root_dir,
                    "{{BASE_DIR}}": base_dir,
                    "{{SYS_BIN}}": config.SYS_BIN,
                    "{{SYS_SYSTEMD}}": config.SYS_SYSTEMD
                }
                for marker, real_value in context_vars.items():
                    if src != "NOT_FOUND": 
                        src = src.replace(marker, real_value)
                    dest = dest.replace(marker, real_value)
                    
                if f_type == "symlink":
                    icon_str = "🔗 [Симлинк]"
                elif f_type == "env":
                    icon_str = "🔐 [ENV]    "
                elif f_type in ["unit", "service"]:
                    icon_str = "⚙️ [Служба] "
                elif f_type == "timer":
                    icon_str = "⏱️ [Таймер] "
                elif f_type == "script":
                    icon_str = "📜 [Скрипт] "
                else:
                    icon_str = "🔹 [Файл]   "
                    
                desc_str = f" ({desc})" if desc else ""
                self.write(f"   {icon_str} {fname}{desc_str} -> {dest}")

