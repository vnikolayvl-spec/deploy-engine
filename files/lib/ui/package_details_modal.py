#!/usr/bin/env python3
"""
Модальное окно управления пакетом при клике на пакет в левой колонке TUI:
- Вкладка «Информация» (описание, статус, все системные пути).
- Вкладка «Лог установки» (последний файл install_DATE.log из /var/lib/de_<pkg>/).
- Вкладка «Логи службы» (статус и журнал systemd / launchd).
- Кнопки: Перезапустить службу, Настроить .env, Переустановить / Удалить / Установить, Закрыть.
"""
from typing import Any, Dict, Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog
from lib.state.package_inspector import PackageInspector


class PackageDetailsModal(ModalScreen):
    """Модальное окно просмотра информации, логов и управления выбранным пакетом."""

    BINDINGS = [
        ("escape", "close_modal", "Закрыть"),
    ]

    def __init__(self, engine, pkg_key: str, env_unit_tuple: Optional[tuple] = None):
        super().__init__()
        self.engine = engine
        self.pkg_key = pkg_key
        self.env_unit_tuple = env_unit_tuple
        self.has_manifest = bool(self.engine and self.engine.registry.has(pkg_key))
        self.is_external = bool(self.has_manifest and self.engine.registry.get(pkg_key).get("is_external_manifest"))
        self.inspector = PackageInspector(state_repo=engine.state_repo, engine=engine)
        self.pkg_info = self.inspector.get_package_info(pkg_key) or {}
        self.pkg_name = self.pkg_info.get("package") or pkg_key.split("/")[-1]
        self.is_installed = bool(self.pkg_info.get("installed"))
        self.service_units = self.inspector.get_package_service_units(pkg_key)

    def compose(self) -> ComposeResult:
        if self.is_installed and not self.has_manifest:
            status_badge = "❗ УСТАНОВЛЕН (манифест удален — доступны служба и логи)"
        elif self.is_installed and self.is_external:
            status_badge = "📌 УСТАНОВЛЕН (внешний манифест)"
        else:
            status_badge = "✅ УСТАНОВЛЕН" if self.is_installed else "⚪ НЕ УСТАНОВЛЕН"
        ver = self.pkg_info.get("version", "1.0.0")
        with Vertical(id="pkg_modal_dialog"):
            yield Label(f"📦 Пакет: {self.pkg_name} (v{ver}) — {status_badge}", id="pkg_modal_title")
            with Horizontal(id="pkg_modal_tabs"):
                yield Button("📋 Информация", variant="primary", id="btn_tab_info")
                yield Button("📜 Лог установки", variant="default", id="btn_tab_install_log")
                yield Button(
                    f"🔧 Логи службы ({len(self.service_units)})",
                    variant="default",
                    id="btn_tab_service_log",
                    disabled=not bool(self.service_units),
                )
            yield RichLog(id="pkg_details_log", markup=False, highlight=False, wrap=True)
            with Horizontal(id="pkg_modal_actions"):
                yield Button(
                    "🔄 Перезапустить службу",
                    variant="warning",
                    id="btn_pkg_restart_srv",
                    disabled=not (self.is_installed and bool(self.service_units)),
                )
                yield Button(
                    "🔐 Настроить .env",
                    variant="default",
                    id="btn_pkg_edit_env",
                    disabled=not (self.has_manifest and bool(self.env_unit_tuple)),
                )
                if self.is_installed:
                    yield Button("🔄 Переустановить", variant="primary", id="btn_pkg_reinstall", disabled=not self.has_manifest)
                    yield Button("🧹 Удалить", variant="error", id="btn_pkg_uninstall", disabled=not self.has_manifest)
                else:
                    yield Button("🎁 Установить", variant="success", id="btn_pkg_install", disabled=not self.has_manifest)
                yield Button("Закрыть (Esc)", variant="default", id="btn_pkg_close")

    def on_mount(self) -> None:
        self._show_tab("info")

    def _show_tab(self, tab_name: str) -> None:
        log_widget = self.query_one("#pkg_details_log", RichLog)
        log_widget.clear()
        for btn_id, t_key in (
            ("#btn_tab_info", "info"),
            ("#btn_tab_install_log", "install_log"),
            ("#btn_tab_service_log", "service_log"),
        ):
            btn = self.query_one(btn_id, Button)
            btn.variant = "primary" if t_key == tab_name else "default"

        if tab_name == "info":
            text = self.inspector.format_package_info(self.pkg_key)
        elif tab_name == "install_log":
            text = self.inspector.get_latest_install_log(self.pkg_key)
        else:
            text = self.inspector.get_service_logs(self.pkg_key)

        for line in text.splitlines() or [""]:
            log_widget.write(line)

    def action_close_modal(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "btn_pkg_close":
            self.dismiss(None)
        elif bid == "btn_tab_info":
            self._show_tab("info")
        elif bid == "btn_tab_install_log":
            self._show_tab("install_log")
        elif bid == "btn_tab_service_log":
            self._show_tab("service_log")
        elif bid == "btn_pkg_restart_srv":
            report = self.inspector.restart_package_services(self.pkg_key)
            log_widget = self.query_one("#pkg_details_log", RichLog)
            log_widget.write("\n" + ("=" * 50))
            for line in report.splitlines():
                log_widget.write(line)
        elif bid == "btn_pkg_edit_env":
            self.dismiss({"action": "edit_env", "pkg_key": self.pkg_key})
        elif bid == "btn_pkg_reinstall":
            self.dismiss({"action": "reinstall", "pkg_key": self.pkg_key})
        elif bid == "btn_pkg_uninstall":
            self.dismiss({"action": "uninstall", "pkg_key": self.pkg_key})
        elif bid == "btn_pkg_install":
            self.dismiss({"action": "install", "pkg_key": self.pkg_key})

