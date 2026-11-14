#!/usr/bin/env python3
"""
Модальное окно выполнения плана и одиночных операций над пакетами непосредственно внутри TUI.
Отображает живой лог выполнения в реальном времени и активирует кнопку закрытия по завершении.
"""
import threading
from typing import Any, Dict, Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog


class ExecutionModal(ModalScreen):
    """Модальное окно выполнения операций (install/reinstall/uninstall/backup/restore) с живым логом."""

    BINDINGS = [
        ("escape", "close_if_done", "Закрыть"),
    ]

    def __init__(self, engine, actions_plan: Dict[str, Any], remote_deployer=None, title: str = "🚀 Выполнение операций"):
        super().__init__()
        self.engine = engine
        self.actions_plan = dict(actions_plan or {})
        self.remote_deployer = remote_deployer
        self.modal_title = title
        self.is_finished = False
        self.succeeded = False

    def compose(self) -> ComposeResult:
        with Vertical(id="exec_modal_dialog"):
            yield Label(self.modal_title, id="exec_modal_title")
            yield Label("⏳ Операция выполняется, пожалуйста подождите...", id="exec_modal_status")
            yield RichLog(id="exec_modal_log", markup=False, highlight=False, wrap=True)
            with Horizontal(id="exec_modal_buttons"):
                yield Button("⏳ Выполняется...", variant="primary", id="btn_exec_close", disabled=True)

    def on_mount(self) -> None:
        worker = threading.Thread(target=self._run_operations_thread, daemon=True)
        worker.start()

    def _append_log_safe(self, text: str) -> None:
        try:
            self.app.call_from_thread(self._write_line, text)
        except Exception:
            pass

    def _write_line(self, text: str) -> None:
        log_widget = self.query_one("#exec_modal_log", RichLog)
        for line in str(text).splitlines() or [""]:
            log_widget.write(line)

    def _on_execution_finished(self, ok: bool, error_msg: Optional[str] = None) -> None:
        self.is_finished = True
        self.succeeded = ok
        status_lbl = self.query_one("#exec_modal_status", Label)
        close_btn = self.query_one("#btn_exec_close", Button)
        log_widget = self.query_one("#exec_modal_log", RichLog)
        if ok:
            status_lbl.update("✅ Все операции успешно завершены.")
            close_btn.label = "✅ Готово — Закрыть (Esc)"
            close_btn.variant = "success"
        else:
            status_lbl.update(f"❌ Завершено с ошибкой: {error_msg or 'сбой операции'}")
            log_widget.write(f"\n❌ ОШИБКА: {error_msg}")
            close_btn.label = "Закрыть (Esc)"
            close_btn.variant = "error"
        close_btn.disabled = False
        close_btn.focus()

    def execute_plan_synchronously(self) -> None:
        """Выполняет шаги плана в строгом порядке: backup -> restore -> uninstall -> reinstall -> install."""
        if self.remote_deployer:
            self.remote_deployer.execute_tui_plan(self.actions_plan, self.engine)
            return

        to_backup = [p for p in (self.actions_plan.get("__backup__") or []) if self.engine.registry.has(p)]
        to_restore = {p: s for p, s in (self.actions_plan.get("__restore__") or {}).items() if s and self.engine.registry.has(p)}
        to_uninstall = [k for k, v in self.actions_plan.items() if v == "uninstall" and self.engine.registry.has(k)]
        to_reinstall = [k for k, v in self.actions_plan.items() if v == "reinstall" and self.engine.registry.has(k)]
        to_install = [k for k, v in self.actions_plan.items() if v == "install" and self.engine.registry.has(k)]

        if to_backup:
            self.engine.backup_packages(to_backup, comment=getattr(self.engine.context, "comment", ""))
        for pkg, arch_selector in to_restore.items():
            self.engine.restore_packages([pkg], selector=arch_selector)
        for pkg in to_uninstall:
            self.engine.uninstall_package(pkg)
        for pkg in to_reinstall:
            self.engine.reinstall_package(pkg)
        if to_install:
            self.engine.install_packages(to_install)

    def _run_operations_thread(self) -> None:
        self.engine.context.add_log_listener(self._append_log_safe)
        try:
            self.execute_plan_synchronously()
            try:
                self.app.call_from_thread(self._on_execution_finished, True, None)
            except Exception:
                self.is_finished, self.succeeded = True, True
        except Exception as err:
            try:
                self.app.call_from_thread(self._on_execution_finished, False, str(err))
            except Exception:
                self.is_finished, self.succeeded = True, False
        finally:
            self.engine.context.remove_log_listener(self._append_log_safe)

    def action_close_if_done(self) -> None:
        if self.is_finished:
            self.dismiss(self.succeeded)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_exec_close" and self.is_finished:
            self.dismiss(self.succeeded)
