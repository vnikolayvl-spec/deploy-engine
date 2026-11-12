#!/usr/bin/env python3
"""
Кастомный виджет RichLog с включенной цветовой разметкой (markup=True) и фильтрацией по вкладкам пакетов.
Выводит устанавливаемые системные пакеты и юниты сгруппированными поблочно под заголовком каждого пакета.
"""
import os
from typing import List, Optional
from textual.widgets import RichLog


class PlanPreviewLog(RichLog):
    """Виджет рендеринга сводного плана или плана отдельного пакета с поблочной группировкой по пакетам."""

    def __init__(self, engine, app_instance, **kwargs):
        kwargs.setdefault("markup", True)
        kwargs.setdefault("highlight", False)
        super().__init__(**kwargs)
        self.engine = engine
        self.app_ref = app_instance

    def update_plan_view(self, filter_pkg: Optional[str] = None) -> None:
        """Пересчитывает зависимости бэкенда и рендерит лог операций с группировкой юнитов по пакетам."""
        self.clear()

        provider = getattr(self.engine, "provider", None)
        if provider:
            pm = provider.detect_package_manager() or "none"
            if provider.is_sandbox:
                self.write(f"[bold magenta]🛡️ Окружение: Sandbox (эмуляция {provider.distro_id} / {pm})[/bold magenta]")
            else:
                self.write(f"[bold cyan]🌐 Окружение: {provider.distro_id} ({pm})[/bold cyan]")

        plans = {"install": set(), "reinstall": set(), "uninstall": set()}
        for k, v in self.app_ref.actions.items():
            if v in plans and self.engine.registry.has(k) and self.engine.is_package_compatible(k):
                if filter_pkg and k != filter_pkg:
                    continue
                plans[v].add(k)

        if not plans["install"] and not plans["reinstall"] and not plans["uninstall"]:
            self.write("[yellow]Используйте ПРОБЕЛ на пакетах для планирования операций...[/yellow]")
            return

        import deploy_config as config
        paths = provider.get_paths() if provider else {
            "sys_bin": config.SYS_BIN,
            "sys_systemd": config.SYS_SYSTEMD,
        }

        if plans["uninstall"]:
            self.write("[bold red]🚨 ПЛАН УДАЛЕНИЯ ПАКЕТОВ (ЭТАП 1):[/bold red]")
            for pkg in sorted(plans["uninstall"]):
                self.write(f"  [-] Пакет [bold]{pkg}[/bold] будет удален из системы")

        pm_name = provider.detect_package_manager() or "pkg" if provider else "apt-get"

        for mode in ["reinstall", "install"]:
            if not plans[mode]:
                continue
            title = (
                "🔄 ПЛАН ПОЛНОЙ ПЕРЕУСТАНОВКИ (ЭТАП 2):"
                if mode == "reinstall"
                else "🎁 ПЛАН УСТАНОВКИ НОВЫХ ПАКЕТОВ (ЭТАП 3):"
            )
            color = "yellow" if mode == "reinstall" else "green"
            self.write(f"\n[bold {color}]{title}[/bold {color}]")

            self.engine.reset_queue()
            ordered_pkgs: List[str] = []
            selected_names = {self.engine.registry.get(p).get("name", p) for p in plans[mode] if self.engine.registry.has(p)}

            for pkg in sorted(plans[mode]):
                if self.engine.registry.has(pkg):
                    for resolved_pkg in self.engine.resolve_dependencies(pkg):
                        if resolved_pkg not in ordered_pkgs:
                            ordered_pkgs.append(resolved_pkg)

            for idx, pkg_key in enumerate(ordered_pkgs):
                if not self.engine.registry.has(pkg_key):
                    continue
                pkg_info = self.engine.registry.get(pkg_key)
                pkg_name = pkg_info.get("name", pkg_key.split("/")[-1])
                folder_p = pkg_info.get("folder_path", "")
                tree_loc = f"{folder_p}/{pkg_name}" if folder_p else pkg_name
                dep_tag = "" if (pkg_key in plans[mode] or pkg_name in selected_names) else " [yellow](зависимость)[/yellow]"

                prefix_nl = "\n" if idx > 0 else ""
                self.write(
                    f"{prefix_nl}   📂 [bold cyan]Пакет: {pkg_name}[/bold cyan]{dep_tag} [dim](путь в дереве: {tree_loc}/)[/dim]"
                )

                pkg_sys = self.engine.sys_manager.resolve_for_platform(pkg_info.get("sys_packages", []))
                if pkg_sys:
                    self.write(f"      📦 [bold]Системные пакеты ({pm_name}):[/bold] {', '.join(pkg_sys)}")

                base_dir = os.path.abspath(pkg_info.get("base_dir", "."))
                root_dir = os.path.dirname(base_dir)
                context_vars = {
                    "{{ROOT_DIR}}": root_dir,
                    "{{BASE_DIR}}": base_dir,
                    "{{SYS_BIN}}": paths["sys_bin"],
                    "{{SYS_SYSTEMD}}": paths["sys_systemd"],
                }

                for u_name in sorted((pkg_info.get("units") or {}).keys()):
                    fname = f"{pkg_name}:{u_name}"
                    u_spec = (pkg_info.get("units") or {}).get(u_name) or {}
                    src, dest, _, f_type = self.engine.get_paths_and_modes(fname)
                    desc = u_spec.get("desc", "")

                    for marker, real_value in context_vars.items():
                        if src != "NOT_FOUND":
                            src = src.replace(marker, real_value)
                        dest = dest.replace(marker, real_value)

                    if f_type == "symlink":
                        self.write(f"      🔗 [Симлинк] {fname} ({desc}) -> {dest}")
                    elif f_type == "env":
                        preset = self.engine.env_manager.get_local_preset_path(pkg_name)
                        badge = " [bold yellow](предустановка env/)[/bold yellow]" if os.path.isfile(preset) else ""
                        self.write(f"      🔐 [ENV]     {fname}{badge} ({desc}) -> {dest}")
                    else:
                        self.write(f"      🔹 [Файл]    {fname} ({desc}) -> {dest}")

