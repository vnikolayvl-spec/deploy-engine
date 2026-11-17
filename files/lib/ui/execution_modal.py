#!/usr/bin/env python3
"""
Модальное окно выполнения плана и одиночных операций над пакетами внутри TUI.
Содержит вкладку «Общий лог» и отдельные вкладки по каждому устанавливаемому пакету
со встроенным компактным редактором .env, раздельной индикацией принятого .env (🔒)
и галочками завершенной установки пакета (✅) по мере выполнения.
"""
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

from lib.ui.package_env_panel import PackageEnvPanel


class ExecutionModal(ModalScreen):
    """Модальное окно выполнения операций с вкладками по пакетам, редактором .env и потоковым логом."""

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
        self._prepare_package_tabs()

    def _find_pkg_env_unit(self, pkg_key: str) -> Optional[Tuple[str, str, str]]:
        if not self.engine.registry.has(pkg_key):
            return None
        pkg = self.engine.registry.get(pkg_key)
        pkg_name = pkg.get("name", pkg_key.split("/")[-1])
        for u_name, u_spec in sorted((pkg.get("units") or {}).items()):
            if (u_spec or {}).get("type") == "env" or u_name.endswith(".env") or u_name == "deploy.env":
                try:
                    src_path, dest_path, _, _ = self.engine.get_paths_and_modes(f"{pkg_name}:{u_name}")
                    if os.path.isfile(src_path):
                        return u_name, src_path, dest_path
                except Exception:
                    continue
        return None

    def _prepare_package_tabs(self) -> None:
        """Формирует список пакетов для вкладок в порядке их выполнения (пропуская уже установленные зависимости)."""
        raw_order: List[Tuple[str, bool]] = []
        for b_pkg in self.actions_plan.get("__backup__") or []:
            if self.engine.registry.has(b_pkg): raw_order.append((b_pkg, False))
        for r_pkg in (self.actions_plan.get("__restore__") or {}).keys():
            if self.engine.registry.has(r_pkg): raw_order.append((r_pkg, False))
        for k, v in self.actions_plan.items():
            if v == "uninstall" and self.engine.registry.has(k): raw_order.append((k, False))
        for mode in ("reinstall", "install"):
            targets = [k for k, v in self.actions_plan.items() if v == mode and self.engine.registry.has(k)]
            if targets:
                try:
                    resolved, _ = self.engine.dep_graph.resolve_install_order(targets, is_installed_fn=self.engine.state_repo.get_installed_package)
                except Exception:
                    resolved = targets
                for r_key in resolved:
                    if self.engine.registry.has(r_key): raw_order.append((r_key, True))

        for pkg_key, needs_env in raw_order:
            pkg = self.engine.registry.get(pkg_key)
            pkg_name = pkg.get("name", pkg_key.split("/")[-1])
            if pkg_name not in self.ordered_pkg_names:
                self.ordered_pkg_names.append(pkg_name)
                self.pkg_safe_map[pkg_name] = re.sub(r"[^a-zA-Z0-9_-]", "_", pkg_name)
                self.pkg_exec_status[pkg_name] = "pending"
            if needs_env and pkg_name not in self.pkg_env_specs:
                env_spec = self._find_pkg_env_unit(pkg_key)
                if env_spec: self.pkg_env_specs[pkg_name] = env_spec

    def compose(self) -> ComposeResult:
        with Vertical(id="exec_modal_dialog"):
            yield Label(self.modal_title, id="exec_modal_title")
            yield Label("⏳ Операция выполняется, пожалуйста подождите...", id="exec_modal_status")
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

    def on_mount(self) -> None:
        self._switch_active_tab("__general__")
        for pkg_name in self.ordered_pkg_names:
            self._refresh_pkg_tab_label(pkg_name)
        threading.Thread(target=self._run_operations_thread, daemon=True).start()

    def _refresh_pkg_tab_label(self, pkg_name: str) -> None:
        """Обновляет заголовок вкладки пакета, разделяя статус установки (📦/⏳/✅/❌) и статус .env (❗/🔧/🔒)."""
        if not self.is_mounted or pkg_name not in self.pkg_safe_map:
            return
        safe_p = self.pkg_safe_map[pkg_name]
        exec_st = self.pkg_exec_status.get(pkg_name, "pending")
        status_icon = "✅" if exec_st == "done" else ("❌" if exec_st == "error" else ("⏳" if exec_st == "running" else "📦"))
        panel = self.env_panels.get(pkg_name)
        env_badge = (" 🔒" if panel.approved else (" ❗" if panel.has_missing_required_now() else " 🔧")) if panel is not None else ""
        try:
            self.query_one(f"#tab_btn_{safe_p}", Button).label = f"{status_icon} {pkg_name}{env_badge}"
            if panel is not None:
                self.query_one(f"#exec_log_{safe_p}", RichLog).display = bool(panel.approved or panel.locked)
        except Exception:
            pass

    def _on_pkg_env_state_changed(self, pkg_name: str, _approved: bool, _missing_req: bool) -> None:
        self._refresh_pkg_tab_label(pkg_name)

    def _on_pkg_exec_status_safe(self, pkg_name: str, status: str) -> None:
        short_name = (pkg_name or "").split("/")[-1]
        if short_name not in self.pkg_safe_map:
            return
        self.pkg_exec_status[short_name] = status
        try:
            self.app.call_from_thread(self._refresh_pkg_tab_label, short_name)
        except Exception:
            pass

    def _switch_active_tab(self, tab_key: str) -> None:
        if not self.is_mounted:
            return
        self.active_tab = tab_key
        self.query_one("#tab_btn___general__", Button).variant = "primary" if tab_key == "__general__" else "default"
        self.query_one("#exec_modal_log", RichLog).display = (tab_key == "__general__")
        for pkg_name in self.ordered_pkg_names:
            safe_p = self.pkg_safe_map[pkg_name]
            is_cur = (tab_key == pkg_name)
            self.query_one(f"#tab_btn_{safe_p}", Button).variant = "primary" if is_cur else "default"
            self.query_one(f"#exec_pane_{safe_p}", Vertical).display = is_cur
            if is_cur and pkg_name in self.env_panels:
                panel = self.env_panels[pkg_name]
                self.query_one(f"#exec_log_{safe_p}", RichLog).display = bool(panel.approved or panel.locked)

    def _trigger_pkg_env_tab(self, pkg_name: str) -> None:
        """Автоматически открывает вкладку пакета, когда установка дошла до его неподтвержденного .env."""
        self._switch_active_tab(pkg_name)
        self.query_one("#exec_modal_status", Label).update(f"⏸ Подтвердите настройки .env на вкладке пакета «{pkg_name}» и нажмите «Принять .env»...")
        panel = self.env_panels.get(pkg_name)
        if panel: panel.focus_first_input()

    def _finalize_pkg_env_after_approval(self, pkg_name: str) -> None:
        panel = self.env_panels.get(pkg_name)
        if panel: panel.lock_after_install()
        self._refresh_pkg_tab_label(pkg_name)
        if self.is_mounted:
            try: self.query_one("#exec_modal_status", Label).update("⏳ Операция выполняется, пожалуйста подождите...")
            except Exception: pass

    def _await_env_approval_from_thread(self, pkg_name: str, _src_path: str, _dest_path: str) -> Optional[Dict[str, str]]:
        panel = self.env_panels.get(pkg_name)
        if not panel or not self.is_mounted:
            return None
        if not panel.approved:
            self._append_pkg_log_safe(pkg_name, f"⏸ Ожидание подтверждения .env пользователем на вкладке «{pkg_name}»...")
            try: self.app.call_from_thread(self._trigger_pkg_env_tab, pkg_name)
            except Exception: return panel.approved_values
            panel.approval_event.wait()
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
            gen_log.write(line)
            if pkg_log is not None: pkg_log.write(line)

    def _on_execution_finished(self, ok: bool, error_msg: Optional[str] = None) -> None:
        self.is_finished, self.succeeded = True, ok
        status_lbl, close_btn, gen_log = self.query_one("#exec_modal_status", Label), self.query_one("#btn_exec_close", Button), self.query_one("#exec_modal_log", RichLog)
        if ok:
            for pkg_name in self.ordered_pkg_names:
                if self.pkg_exec_status.get(pkg_name) != "done":
                    self.pkg_exec_status[pkg_name] = "done"
                    self._refresh_pkg_tab_label(pkg_name)
            status_lbl.update("✅ Все операции успешно завершены.")
            close_btn.label, close_btn.variant = "✅ Готово — Закрыть (Esc)", "success"
        else:
            status_lbl.update(f"❌ Завершено с ошибкой: {error_msg or 'сбой операции'}")
            gen_log.write(f"\n❌ ОШИБКА: {error_msg}")
            close_btn.label, close_btn.variant = "Закрыть (Esc)", "error"
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
        if to_backup: self.engine.backup_packages(to_backup, comment=getattr(self.engine.context, "comment", ""))
        for pkg, arch_selector in to_restore.items(): self.engine.restore_packages([pkg], selector=arch_selector)
        for pkg in to_uninstall: self.engine.uninstall_package(pkg)
        for pkg in to_reinstall: self.engine.reinstall_package(pkg)
        if to_install: self.engine.install_packages(to_install)

    def _run_operations_thread(self) -> None:
        prev_in_tui, prev_cb = bool(getattr(self.engine.context, "in_tui", False)), getattr(self.engine.context, "env_approval_callback", None)
        self.engine.context.in_tui, self.engine.context.env_approval_callback = True, self._await_env_approval_from_thread
        self.engine.context.add_pkg_log_listener(self._append_pkg_log_safe)
        self.engine.context.add_pkg_status_listener(self._on_pkg_exec_status_safe)
        try:
            self.execute_plan_synchronously()
            try: self.app.call_from_thread(self._on_execution_finished, True, None)
            except Exception: self.is_finished, self.succeeded = True, True
        except Exception as err:
            try: self.app.call_from_thread(self._on_execution_finished, False, str(err))
            except Exception: self.is_finished, self.succeeded = True, False
        finally:
            self.engine.context.remove_pkg_status_listener(self._on_pkg_exec_status_safe)
            self.engine.context.remove_pkg_log_listener(self._append_pkg_log_safe)
            self.engine.context.env_approval_callback, self.engine.context.in_tui = prev_cb, prev_in_tui

    def action_close_if_done(self) -> None:
        if self.is_finished: self.dismiss(self.succeeded)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "btn_exec_close" and self.is_finished:
            self.dismiss(self.succeeded)
        elif btn_id == "tab_btn___general__":
            self._switch_active_tab("__general__")
        elif btn_id.startswith("tab_btn_"):
            safe_target = btn_id[len("tab_btn_") :]
            for pkg_name, safe_p in self.pkg_safe_map.items():
                if safe_p == safe_target:
                    self._switch_active_tab(pkg_name)
                    break
