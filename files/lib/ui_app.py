#!/usr/bin/env python3
"""
Главный диспетчер интерфейса (Screen Controller) Deploy Engine.
Трехколоночный макет:
- Слева на всю высоту: вертикальный список пакетов (с запланированными действиями вверху и установленными ниже).
- По центру: дерево пакетов сверху, панель плана с быстрым доступом к .env [E] и лог плана снизу.
- Справа на всю высоту: настройки Sandbox сверху и кнопки «Выполнить план» / «Выход» внизу.
"""
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, OptionList, Select, Tree
from textual.widgets.option_list import Option
from textual.widgets.tree import TreeNode

from lib.ui.env_editor_modal import EnvEditorModal
from lib.ui.execution_modal import ExecutionModal
from lib.ui.package_details_modal import PackageDetailsModal
from lib.ui.package_tree import InfrastructureTree
from lib.ui.plan_preview import PlanPreviewLog
from lib.ui.styles import APP_CSS
from lib.utils import dispatch_localized_binding, normalize_hotkey


class DeployApp(App):
    TITLE = "Independent Multi-Action Deployer"
    CSS = APP_CSS
    BINDINGS = [("e", "edit_current_env", "Настроить .env")]

    SANDBOX_OS_OPTIONS = [
        ("macOS (brew / launchd)", "macos"),
        ("Debian (apt / systemd)", "debian"),
        ("Ubuntu (apt / systemd)", "ubuntu"),
        ("Alpine (apk)", "alpine"),
        ("Arch Linux (pacman)", "arch"),
        ("Fedora / RHEL (dnf)", "fedora"),
    ]

    def __init__(self, engine, remote_deployer=None):
        super().__init__()
        self.engine = engine
        self.remote_deployer = remote_deployer
        self.actions: Dict[str, str] = {}
        self.backup_plans: Set[str] = set()
        self.restore_plans: Dict[str, str] = {}
        self._last_q_time: float = 0.0
        self._last_tabs_sig: Optional[tuple] = None
        self.option_pkg_map: List[Optional[str]] = [None]
        self.selected_filter_pkg: Optional[str] = None
        self.cursor_pkg_key: Optional[str] = None

    def compose(self) -> ComposeResult:
        is_sb = bool(getattr(self.engine.provider, "is_sandbox", False))
        remote_host = getattr(self.engine.context, "remote", None)
        remote_dir = getattr(self.engine.context, "remote_dir", "/opt/de_deploy-engine")
        cur_distro = getattr(self.engine.provider, "distro_id", "debian")
        valid_os = {val for _, val in self.SANDBOX_OS_OPTIONS}
        initial_os = cur_distro if cur_distro in valid_os else ("macos" if getattr(self.engine.provider, "os_family", "") == "macos" else "debian")

        yield Header(show_clock=True)
        with Horizontal(id="main_layout"):
            with Vertical(id="left_sidebar"):
                yield Label("📦 Пакеты (клик — инфо/логи)", classes="sidebar_title")
                yield OptionList(Option("📋 Все пакеты"), id="plan_pkg_list")
                yield Button("🔐 Настроить .env [E]", variant="warning", id="btn_edit_pkg_env", disabled=True)

            with Vertical(id="center_column"):
                yield Label("Управление: Пробел — выбор пакета/бэкапа/архива, Вправо/Влево — раскрыть/свернуть (Вправо на ENV — .env, q-q — выход)")
                yield InfrastructureTree(self.engine, self, id="packages_tree")
                yield Label("📋 Предпросмотр плана: Все пакеты", id="lbl_plan_title")
                yield PlanPreviewLog(self.engine, self, id="preview_log")

            with Vertical(id="right_sidebar"):
                with Vertical(id="settings_box"):
                    yield Label("🔧 Настройки", classes="sidebar_title")
                    if remote_host:
                        yield Label(f"🌐 Сервер: {remote_host}\n📂 {remote_dir}", id="lbl_remote_info")
                    yield Checkbox("🔒 Sandbox (песочница)", value=is_sb, id="chk_sandbox", disabled=bool(remote_host))
                    yield Label("Система песочницы:", id="lbl_sandbox_os")
                    yield Select(self.SANDBOX_OS_OPTIONS, value=initial_os, allow_blank=False, id="sel_sandbox_os", disabled=bool(remote_host))
                    yield Label("📁 Предустановки .env:\ndeploy-engine/env/", id="lbl_env_dir_hint")

                with Vertical(id="action_buttons_box"):
                    yield Button("Выполнить план", variant="success", id="btn_run")
                    yield Button("Выход [q-q]", variant="error", id="btn_exit")
        yield Footer()

    def on_mount(self) -> None:
        remote_host = getattr(self.engine.context, "remote", None)
        if remote_host:
            self.title = f"Deploy Engine [REMOTE: {remote_host}]"
        self.render_live_preview()
        self.query_one("#packages_tree", InfrastructureTree).focus()

    def _find_package_env_unit(self, pkg_key: Optional[str]) -> Optional[Tuple[str, str, str, str]]:
        """Ищет .env юнит у пакета и возвращает (pkg_name, unit_name, src_path, dest_path)."""
        if not pkg_key or not self.engine.registry.has(pkg_key): return None
        pkg = self.engine.registry.get(pkg_key)
        pkg_name = pkg.get("name", pkg_key.split("/")[-1])
        for u_name, u_spec in sorted((pkg.get("units") or {}).items()):
            if (u_spec or {}).get("type") == "env" or u_name.endswith(".env") or u_name == "deploy.env":
                try:
                    src_path, dest_path, _, _ = self.engine.get_paths_and_modes(f"{pkg_name}:{u_name}")
                    if os.path.isfile(src_path): return pkg_name, u_name, src_path, dest_path
                except Exception: continue
        return None

    def _resolve_active_env_target(self) -> Optional[Tuple[str, str, str, str]]:
        return self._find_package_env_unit(self.selected_filter_pkg) if self.selected_filter_pkg else None

    def _update_env_button_state(self) -> None:
        self.query_one("#lbl_plan_title", Label).update(f"📋 Предпросмотр плана: {self.selected_filter_pkg or 'Все пакеты'}")
        env_btn, env_target = self.query_one("#btn_edit_pkg_env", Button), self._resolve_active_env_target()
        if env_target:
            preset_exists = os.path.isfile(self.engine.env_manager.get_local_preset_path(env_target[0]))
            env_btn.label, env_btn.disabled = f"🔐 {'✓ ' if preset_exists else ''}Настроить .env [E]", False
        else:
            env_btn.label, env_btn.disabled = "🔐 Настроить .env [E]", True

    def _resolve_installed_keys(self) -> Set[str]:
        state_data = self.engine.state_repo.get_state() if getattr(self.engine, "state_repo", None) else {}
        installed_map = state_data.get("installed", {}) or state_data.get("installed_packages", {})
        resolved: Set[str] = set()
        for k, info in installed_map.items():
            ns = (info or {}).get("namespace") or k
            target_key = ns if self.engine.registry.has(ns) else (k if self.engine.registry.has(k) else ns)
            if not self.engine.registry.has(target_key) and hasattr(self.engine.registry, "register_external_manifest"):
                mf_path = (info or {}).get("manifest_path", "")
                if mf_path: self.engine.registry.register_external_manifest(mf_path, target_key)
            resolved.add(target_key)
        return resolved

    def _sync_plan_tabs(self) -> None:
        """Обновляет левый список: пакеты с действиями вверху списка, установленные без действий — ниже."""
        opt_list, installed_keys = self.query_one("#plan_pkg_list", OptionList), self._resolve_installed_keys()
        planned_keys = {k for k, v in self.actions.items() if v in ("install", "reinstall", "uninstall")} | set(self.backup_plans) | {k for k, v in self.restore_plans.items() if v}
        all_candidates = sorted([k for k in (installed_keys | planned_keys) if not self.engine.registry.has(k) or self.engine.is_package_compatible(k)], key=lambda k: (0 if k in planned_keys else 1, k))
        current_sig = tuple((k, k in installed_keys, self.engine.registry.has(k), self.actions.get(k, ""), k in self.backup_plans, self.restore_plans.get(k, "")) for k in all_candidates)
        if current_sig == self._last_tabs_sig: return
        self._last_tabs_sig = current_sig
        if self.selected_filter_pkg not in all_candidates: self.selected_filter_pkg = None

        icons = {"install": "[bold green]+[/bold green]", "reinstall": "[bold yellow]↻[/bold yellow]", "uninstall": "[bold red]-[/bold red]"}
        opt_list.clear_options()
        opt_list.add_option(Option(f"📋 Все пакеты ({len(planned_keys)})" if planned_keys else "📋 Все пакеты"))
        new_map: List[Optional[str]] = [None]
        selected_idx = 0

        for idx, pkg_key in enumerate(all_candidates, start=1):
            act, has_mf = self.actions.get(pkg_key, "none"), self.engine.registry.has(pkg_key)
            is_ext = bool(has_mf and self.engine.registry.get(pkg_key).get("is_external_manifest"))
            default_badge = "[bold yellow]![/bold yellow]" if not has_mf else ("[bold cyan]✓[/bold cyan]" if is_ext else "[bold green]✓[/bold green]")
            badges: List[str] = [icons[act]] if act in icons else ([default_badge] if pkg_key in installed_keys and pkg_key not in planned_keys else [])
            if pkg_key in self.backup_plans: badges.append("💾")
            if self.restore_plans.get(pkg_key): badges.append("🔄")
            suffix = " [dim](манифест удален)[/dim]" if not has_mf else (" [dim](внешний)[/dim]" if is_ext else "")
            opt_list.add_option(Option(f"{''.join(badges) or default_badge} {pkg_key}{suffix}"))
            new_map.append(pkg_key)
            if pkg_key == self.selected_filter_pkg: selected_idx = idx

        self.option_pkg_map, opt_list.highlighted = new_map, selected_idx

    def render_live_preview(self) -> None:
        self._sync_plan_tabs()
        self._update_env_button_state()
        self.query_one("#preview_log", PlanPreviewLog).update_plan_view(filter_pkg=self.selected_filter_pkg)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "plan_pkg_list" and 0 <= event.option_index < len(self.option_pkg_map):
            self.selected_filter_pkg = self.option_pkg_map[event.option_index]
            self._update_env_button_state()
            self.query_one("#preview_log", PlanPreviewLog).update_plan_view(filter_pkg=self.selected_filter_pkg)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "plan_pkg_list" and 0 <= event.option_index < len(self.option_pkg_map):
            self.selected_filter_pkg = self.option_pkg_map[event.option_index]
            self._update_env_button_state()
            self.query_one("#preview_log", PlanPreviewLog).update_plan_view(filter_pkg=self.selected_filter_pkg)
            if self.selected_filter_pkg:
                self._open_package_details_modal(self.selected_filter_pkg)

    def _open_package_details_modal(self, pkg_key: str) -> None:
        env_tuple = self._find_package_env_unit(pkg_key)

        def _on_details_closed(res: Optional[Dict[str, Any]]) -> None:
            if not res or not isinstance(res, dict): return
            act, target_pkg = res.get("action"), res.get("pkg_key", pkg_key)
            if act == "edit_env" and env_tuple: self._launch_env_modal(*env_tuple)
            elif act in ("install", "reinstall", "uninstall"): self._run_plan_in_modal({target_pkg: act}, clear_current_plan=False)

        self.push_screen(PackageDetailsModal(self.engine, pkg_key, env_unit_tuple=env_tuple), _on_details_closed)

    def _run_plan_in_modal(self, plan_dict: Dict[str, Any], clear_current_plan: bool = True) -> None:
        def _on_exec_closed(_ok: Any) -> None:
            if clear_current_plan:
                self.actions.clear(); self.backup_plans.clear(); self.restore_plans.clear()
            else:
                for k in plan_dict:
                    if not k.startswith("__"): self.actions.pop(k, None)
            if self.remote_deployer:
                try: self.remote_deployer.prepare_remote_tui(self.engine)
                except Exception: pass
            self._last_tabs_sig = None
            self.query_one("#packages_tree", InfrastructureTree).rebuild_tree()
            self.render_live_preview()

        self.push_screen(ExecutionModal(self.engine, plan_dict, remote_deployer=self.remote_deployer), _on_exec_closed)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if event.node and event.node.data:
            self.cursor_pkg_key = event.node.data.get("key") if event.node.data.get("is_package") else (event.node.data.get("pkg_key") or event.node.data.get("pkg_name"))
            self._update_env_button_state()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "chk_sandbox":
            self._apply_sandbox_settings(event.value, str(self.query_one("#sel_sandbox_os", Select).value))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sel_sandbox_os" and self.query_one("#chk_sandbox", Checkbox).value:
            self._apply_sandbox_settings(True, str(event.value))

    def _apply_sandbox_settings(self, sandbox_enabled: bool, sandbox_os: str) -> None:
        self.engine.configure_environment(sandbox=sandbox_enabled, sandbox_os=sandbox_os)
        self._last_tabs_sig = None
        self.query_one("#packages_tree", InfrastructureTree).rebuild_tree()
        self.render_live_preview()

    def _launch_env_modal(self, pkg_name: str, unit_name: str, src_path: str, dest_path: str) -> None:
        def _on_modal_closed(saved_preset_path: Optional[str]) -> None:
            if saved_preset_path:
                self.query_one("#packages_tree", InfrastructureTree).mark_env_configured(pkg_name)
                self.render_live_preview()
        self.push_screen(EnvEditorModal(self.engine, pkg_name, unit_name, src_path, dest_path), _on_modal_closed)

    def open_env_editor(self, env_node: TreeNode) -> None:
        if not env_node.data: return
        pkg_name, unit_name = env_node.data.get("pkg_name", ""), env_node.data.get("unit_name", "deploy.env")
        try:
            src_path, dest_path, _, _ = self.engine.get_paths_and_modes(f"{pkg_name}:{unit_name}")
            if os.path.isfile(src_path): self._launch_env_modal(pkg_name, unit_name, src_path, dest_path)
        except Exception:
            return

    def action_edit_current_env(self) -> None:
        target = self._resolve_active_env_target()
        if target: self._launch_env_modal(*target)

    def on_key(self, event) -> None:
        if isinstance(self.focused, Input):
            return
        norm_key = normalize_hotkey(getattr(event, "key", "") or "", getattr(event, "character", "") or "")
        if norm_key == "q":
            event.prevent_default()
            event.stop()
            now = time.monotonic()
            if now - self._last_q_time <= 1.0:
                self.exit()
            else:
                self._last_q_time = now
                self.notify("Нажмите q (й) ещё раз в течение 1 сек для выхода", severity="warning", timeout=1.0)
        else:
            dispatch_localized_binding(self, event)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_exit":
            self.exit()
        elif event.button.id == "btn_edit_pkg_env":
            self.action_edit_current_env()
        elif event.button.id == "btn_run":
            active_targets: Dict[str, Any] = {
                k: v for k, v in self.actions.items() if v != "none" and self.engine.registry.has(k) and self.engine.is_package_compatible(k)
            }
            backups = sorted(k for k in self.backup_plans if self.engine.registry.has(k) and self.engine.is_package_compatible(k))
            restores = {k: v for k, v in self.restore_plans.items() if v and self.engine.registry.has(k) and self.engine.is_package_compatible(k)}
            if not active_targets and not backups and not restores:
                self.query_one("#preview_log", PlanPreviewLog).write(
                    "[bold red]❌ План пуст! Выберите пакеты, пункт бэкапа или архив восстановления клавишей ПРОБЕЛ.[/bold red]"
                )
                return
            if backups:
                active_targets["__backup__"] = backups
            if restores:
                active_targets["__restore__"] = restores
            self._run_plan_in_modal(active_targets, clear_current_plan=True)

