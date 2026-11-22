#!/usr/bin/env python3
"""
Модальное окно выполнения плана и одиночных операций над пакетами внутри TUI.
Содержит вкладку «Общий лог» и отдельные вкладки по каждому устанавливаемому пакету,
обязательное подтверждение .env до начала установки, время [HH:MM:SS] в логах,
автоочистку логов при новой установке и неблокирующий спиннер с таймером [MM:SS].
"""
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

from lib.ui.activity_indicator import ActivityIndicator
from lib.ui.package_env_panel import PackageEnvPanel
from lib.ui.plan_executor import PlanExecutor


class ExecutionModal(ModalScreen):
    """Модальное окно выполнения операций с вкладками, барьером .env, спиннером и потоковым логом."""

    BINDINGS = [("escape", "close_if_done", "Закрыть")]

    def __init__(self, engine, actions_plan: Dict[str, Any], remote_deployer=None, title: str = "🚀 Выполнение операций"):
        super().__init__()
        self.engine, self.actions_plan, self.remote_deployer, self.modal_title = engine, dict(actions_plan or {}), remote_deployer, title
        self.is_finished, self.succeeded, self.active_tab = False, False, "__general__"
        self.ordered_pkg_names: List[str] = []
        self.pkg_safe_map: Dict[str, str] = {}
        self.pkg_env_specs: Dict[str, Tuple[str, str, str]] = {}
        self.env_panels: Dict[str, PackageEnvPanel] = {}
        self.pkg_exec_status: Dict[str, str] = {}
        self.indicator = ActivityIndicator()
        self._spinner_timer = None
        self._prepare_package_tabs()

    def _prepare_package_tabs(self) -> None:
        """Формирует список пакетов для вкладок в порядке их выполнения (пропуская уже установленные зависимости)."""
        self.ordered_pkg_names, self.pkg_env_specs = PlanExecutor.build_ordered_items(self.engine, self.actions_plan)
        for pkg_name in self.ordered_pkg_names:
            self.pkg_safe_map[pkg_name] = re.sub(r"[^a-zA-Z0-9_-]", "_", pkg_name)
            self.pkg_exec_status[pkg_name] = "pending"

    def compose(self) -> ComposeResult:
        with Vertical(id="exec_modal_dialog"):
            yield Label(self.modal_title, id="exec_modal_title")
            yield Label(self.indicator.render_status(advance=False), id="exec_modal_status")
            with Horizontal(id="exec_modal_tabs"):
                yield Button("📋 Общий лог", variant="primary", id="tab_btn___general__", classes="exec_tab_btn")
                for pkg_name in self.ordered_pkg_names:
                    safe_p = self.pkg_safe_map[pkg_name]
                    yield Button(f"📦 {pkg_name}", variant="default", id=f"tab_btn_{safe_p}", classes="exec_tab_btn")

            with Vertical(id="exec_panes_container"):
                yield RichLog(id="exec_modal_log", markup=False, highlight=False, wrap=True)
                for pkg_name in self.ordered_pkg_names:
                    safe_p = self.pkg_safe_map[pkg_name]
                    with Vertical(id=f"exec_pane_{safe_p}", classes="exec_pkg_pane"):
                        if pkg_name in self.pkg_env_specs:
                            u_name, src_p, dest_p = self.pkg_env_specs[pkg_name]
                            panel = PackageEnvPanel(
                                self.engine, pkg_name, u_name, src_p, dest_p,
                                on_state_change=self._on_pkg_env_state_changed, id=f"env_panel_{safe_p}",
                            )
                            self.env_panels[pkg_name] = panel
                            yield panel
                        yield RichLog(id=f"exec_log_{safe_p}", classes="exec_pkg_log", markup=False, highlight=False, wrap=True)

            with Horizontal(id="exec_modal_buttons"):
                yield Button("⏳ Выполняется...", variant="primary", id="btn_exec_close", disabled=True)

    def clear_all_logs(self) -> None:
        """Очищает общий лог и все вкладки логов пакетов перед началом новой установки."""
        try: self.query_one("#exec_modal_log", RichLog).clear()
        except Exception: pass
        for pkg_name in self.ordered_pkg_names:
            try: self.query_one(f"#exec_log_{self.pkg_safe_map[pkg_name]}", RichLog).clear()
            except Exception: pass

    def _tick_activity_indicator(self) -> None:
        """Обновляет неблокирующий спиннер и счетчик времени [MM:SS] в строке статуса."""
        if self.is_finished or not self.is_mounted: return
        status_text = self.indicator.render_status(advance=True)
        try: self.query_one("#exec_modal_status", Label).update(status_text)
        except Exception: pass
        try:
            frame = ActivityIndicator.SPINNER_FRAMES[(self.indicator.frame_idx - 1) % len(ActivityIndicator.SPINNER_FRAMES)]
            btn_lbl = "⏸ Ожидание .env..." if self.indicator.paused_message else f"{frame} Выполняется [{self.indicator.format_elapsed()}]"
            self.query_one("#btn_exec_close", Button).label = btn_lbl
        except Exception: pass

    def _on_phase_change_safe(self, phase: str) -> None:
        self.indicator.set_phase(phase)
        if not self.is_finished and self.is_mounted:
            try: self.app.call_from_thread(self._tick_activity_indicator)
            except Exception: pass

    def on_mount(self) -> None:
        self.indicator.reset()
        self.clear_all_logs()
        self._switch_active_tab("__general__")
        for pkg_name in self.ordered_pkg_names:
            self._refresh_pkg_tab_label(pkg_name)
        if hasattr(self, "set_interval"):
            self._spinner_timer = self.set_interval(0.25, self._tick_activity_indicator)
        threading.Thread(target=self._run_operations_thread, daemon=True).start()

    def _refresh_pkg_tab_label(self, pkg_name: str) -> None:
        """Обновляет заголовок вкладки пакета, разделяя статус установки (📦/⏳/✅/❌) и статус .env (❗/🔧/🔒)."""
        if not self.is_mounted or pkg_name not in self.pkg_safe_map: return
        safe_p = self.pkg_safe_map[pkg_name]
        exec_st = self.pkg_exec_status.get(pkg_name, "pending")
        status_icon = "✅" if exec_st == "done" else ("❌" if exec_st == "error" else ("⏳" if exec_st == "running" else "📦"))
        panel = self.env_panels.get(pkg_name)
        env_badge = (" 🔒" if panel.approved else (" ❗" if panel.has_missing_required_now() else " 🔧")) if panel is not None else ""
        try:
            self.query_one(f"#tab_btn_{safe_p}", Button).label = f"{status_icon} {pkg_name}{env_badge}"
            if panel is not None: self.query_one(f"#exec_log_{safe_p}", RichLog).display = bool(panel.approved or panel.locked)
        except Exception: pass

    def _on_pkg_env_state_changed(self, pkg_name: str, _approved: bool, _missing_req: bool) -> None:
        self._refresh_pkg_tab_label(pkg_name)

    def _on_pkg_exec_status_safe(self, pkg_name: str, status: str) -> None:
        short_name = (pkg_name or "").split("/")[-1]
        if short_name not in self.pkg_safe_map: return
        self.pkg_exec_status[short_name] = status
        try: self.app.call_from_thread(self._refresh_pkg_tab_label, short_name)
        except Exception: pass

    def _switch_active_tab(self, tab_key: str) -> None:
        if not self.is_mounted: return
        self.active_tab = tab_key
        self.query_one("#tab_btn___general__", Button).variant = "primary" if tab_key == "__general__" else "default"
        self.query_one("#exec_modal_log", RichLog).display = (tab_key == "__general__")
        for pkg_name in self.ordered_pkg_names:
            safe_p, is_cur = self.pkg_safe_map[pkg_name], (tab_key == pkg_name)
            self.query_one(f"#tab_btn_{safe_p}", Button).variant = "primary" if is_cur else "default"
            self.query_one(f"#exec_pane_{safe_p}", Vertical).display = is_cur
            if is_cur and pkg_name in self.env_panels:
                panel = self.env_panels[pkg_name]
                self.query_one(f"#exec_log_{safe_p}", RichLog).display = bool(panel.approved or panel.locked)

    def _trigger_pkg_env_tab(self, pkg_name: str) -> None:
        self._switch_active_tab(pkg_name)
        pause_msg = f"⏸ Подтвердите настройки .env на вкладке пакета «{pkg_name}» и нажмите «Принять .env»..."
        self.indicator.pause(pause_msg)
        self.query_one("#exec_modal_status", Label).update(pause_msg)
        panel = self.env_panels.get(pkg_name)
        if panel: panel.focus_first_input()

    def _finalize_pkg_env_after_approval(self, pkg_name: str) -> None:
        panel = self.env_panels.get(pkg_name)
        if panel: panel.lock_after_install()
        self._refresh_pkg_tab_label(pkg_name)
        self.indicator.resume()
        if self.is_mounted:
            try: self.query_one("#exec_modal_status", Label).update(self.indicator.render_status(advance=False))
            except Exception: pass

    def _run_pre_install_env_barrier(self) -> bool:
        """Обязательный барьер подтверждения .env ДО запуска apt/brew и установки файлов."""
        pending = [p for p in self.ordered_pkg_names if p in self.env_panels and not self.env_panels[p].approved]
        if not pending: return True
        self._append_pkg_log_safe(None, f"🔐 Обязательное подтверждение .env до начала установки ({len(pending)} шт.): {', '.join(pending)}")
        for pkg_name in pending:
            panel = self.env_panels[pkg_name]
            if panel.approved: continue
            self._append_pkg_log_safe(pkg_name, f"⏸ Ожидание обязательного подтверждения .env для «{pkg_name}» до начала установки...")
            try: self.app.call_from_thread(self._trigger_pkg_env_tab, pkg_name)
            except Exception: return not panel.cancelled
            panel.approval_event.wait()
            if getattr(panel, "cancelled", False):
                self._append_pkg_log_safe(pkg_name, f"❗ Установка отменена пользователем до начала развертывания (пакет «{pkg_name}»).")
                return False
            try: self.app.call_from_thread(self._finalize_pkg_env_after_approval, pkg_name)
            except Exception: pass
        try: self.app.call_from_thread(self._switch_active_tab, "__general__")
        except Exception: pass
        return True

    def _await_env_approval_from_thread(self, pkg_name: str, _src_path: str, _dest_path: str) -> Optional[Dict[str, str]]:
        panel = self.env_panels.get(pkg_name)
        if not panel or not self.is_mounted: return None
        if not panel.approved:
            self._append_pkg_log_safe(pkg_name, f"⏸ Ожидание подтверждения .env пользователем на вкладке «{pkg_name}»...")
            try: self.app.call_from_thread(self._trigger_pkg_env_tab, pkg_name)
            except Exception: return panel.approved_values
            panel.approval_event.wait()
            if getattr(panel, "cancelled", False): raise RuntimeError(f"Установка отменена пользователем на этапе .env ({pkg_name})")
        try: self.app.call_from_thread(self._finalize_pkg_env_after_approval, pkg_name)
        except Exception: pass
        return dict(panel.approved_values)

    def _append_pkg_log_safe(self, pkg_name: Optional[str], text: str) -> None:
        try: self.app.call_from_thread(self._write_line, pkg_name, text)
        except Exception: pass

    def _write_line(self, pkg_name: Optional[str], text: str) -> None:
        gen_log = self.query_one("#exec_modal_log", RichLog)
        pkg_log = None
        if pkg_name and pkg_name in self.pkg_safe_map:
            try: pkg_log = self.query_one(f"#exec_log_{self.pkg_safe_map[pkg_name]}", RichLog)
            except Exception: pkg_log = None
        for line in str(text).splitlines() or [""]:
            stamped = ActivityIndicator.format_log_line(line)
            gen_log.write(stamped)
            if pkg_log is not None: pkg_log.write(stamped)

    def _on_execution_finished(self, ok: bool, error_msg: Optional[str] = None) -> None:
        self.is_finished, self.succeeded = True, ok
        if self._spinner_timer is not None:
            try: self._spinner_timer.stop()
            except Exception: pass
        elapsed = self.indicator.format_elapsed()
        status_lbl, close_btn, gen_log = self.query_one("#exec_modal_status", Label), self.query_one("#btn_exec_close", Button), self.query_one("#exec_modal_log", RichLog)
        if ok:
            for pkg_name in self.ordered_pkg_names:
                if self.pkg_exec_status.get(pkg_name) != "done":
                    self.pkg_exec_status[pkg_name] = "done"
                    self._refresh_pkg_tab_label(pkg_name)
            status_lbl.update(f"✅ Все операции успешно завершены [{elapsed}].")
            close_btn.label, close_btn.variant = "✅ Готово — Закрыть (Esc)", "success"
        else:
            status_lbl.update(f"❌ Завершено с ошибкой [{elapsed}]: {error_msg or 'сбой операции'}")
            gen_log.write(ActivityIndicator.format_log_line(f"❌ ОШИБКА: {error_msg}"))
            close_btn.label, close_btn.variant = "Закрыть (Esc)", "error"
        close_btn.disabled = False
        close_btn.focus()

    def execute_plan_synchronously(self) -> None:
        PlanExecutor.execute_plan(self.engine, self.actions_plan, remote_deployer=self.remote_deployer)

    def _run_operations_thread(self) -> None:
        prev_in_tui, prev_cb = bool(getattr(self.engine.context, "in_tui", False)), getattr(self.engine.context, "env_approval_callback", None)
        self.engine.context.in_tui, self.engine.context.env_approval_callback = True, self._await_env_approval_from_thread
        self.engine.context.add_pkg_log_listener(self._append_pkg_log_safe)
        self.engine.context.add_pkg_status_listener(self._on_pkg_exec_status_safe)
        self.engine.context.add_phase_listener(self._on_phase_change_safe)
        try:
            if not self._run_pre_install_env_barrier():
                try: self.app.call_from_thread(self._on_execution_finished, False, "Операция отменена пользователем на этапе подтверждения .env.")
                except Exception: self.is_finished, self.succeeded = True, False
                return
            self.execute_plan_synchronously()
            try: self.app.call_from_thread(self._on_execution_finished, True, None)
            except Exception: self.is_finished, self.succeeded = True, True
        except Exception as err:
            try: self.app.call_from_thread(self._on_execution_finished, False, str(err))
            except Exception: self.is_finished, self.succeeded = True, False
        finally:
            self.engine.context.remove_phase_listener(self._on_phase_change_safe)
            self.engine.context.remove_pkg_status_listener(self._on_pkg_exec_status_safe)
            self.engine.context.remove_pkg_log_listener(self._append_pkg_log_safe)
            self.engine.context.env_approval_callback, self.engine.context.in_tui = prev_cb, prev_in_tui

    def action_close_if_done(self) -> None:
        if self.is_finished: self.dismiss(self.succeeded)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "btn_exec_close" and self.is_finished: self.dismiss(self.succeeded)
        elif btn_id == "tab_btn___general__": self._switch_active_tab("__general__")
        elif btn_id.startswith("tab_btn_"):
            safe_target = btn_id[len("tab_btn_") :]
            for pkg_name, safe_p in self.pkg_safe_map.items():
                if safe_p == safe_target:
                    self._switch_active_tab(pkg_name)
                    break
