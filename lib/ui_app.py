#!/usr/bin/env python3
"""
Главный диспетчер интерфейса (Screen Controller) Deploy Engine.
Трехколоночный макет:
- Слева на всю высоту: вертикальный список вкладок выбранных пакетов.
- По центру: дерево пакетов сверху, панель плана с быстрым доступом к .env [E] и лог плана снизу.
- Справа на всю высоту: настройки Sandbox сверху и кнопки «Выполнить план» / «Выход» внизу.
"""
import os
from typing import Dict, List, Optional, Tuple
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Footer, Header, Label, OptionList, Select, Tree
from textual.widgets.option_list import Option
from textual.widgets.tree import TreeNode

from lib.ui.env_editor_modal import EnvEditorModal
from lib.ui.package_tree import InfrastructureTree
from lib.ui.plan_preview import PlanPreviewLog
from lib.ui.styles import APP_CSS


class DeployApp(App):
    TITLE = "Independent Multi-Action Deployer"
    CSS = APP_CSS

    BINDINGS = [
        ("e", "edit_current_env", "Настроить .env"),
    ]

    SANDBOX_OS_OPTIONS = [
        ("macOS (brew / launchd)", "macos"),
        ("Debian (apt / systemd)", "debian"),
        ("Ubuntu (apt / systemd)", "ubuntu"),
        ("Alpine (apk)", "alpine"),
        ("Arch Linux (pacman)", "arch"),
        ("Fedora / RHEL (dnf)", "fedora"),
    ]

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.actions: Dict[str, str] = {}
        self._last_tabs_sig: Optional[tuple] = None
        self.option_pkg_map: List[Optional[str]] = [None]
        self.selected_filter_pkg: Optional[str] = None
        self.cursor_pkg_key: Optional[str] = None

    def compose(self) -> ComposeResult:
        is_sb = bool(getattr(self.engine.provider, "is_sandbox", False))
        cur_distro = getattr(self.engine.provider, "distro_id", "debian")
        valid_os_values = {val for _, val in self.SANDBOX_OS_OPTIONS}
        initial_os = cur_distro if cur_distro in valid_os_values else (
            "macos" if getattr(self.engine.provider, "os_family", "") == "macos" else "debian"
        )

        yield Header(show_clock=True)
        with Horizontal(id="main_layout"):
            with Vertical(id="left_sidebar"):
                yield Label("📋 Пакеты в плане", classes="sidebar_title")
                yield OptionList(Option("📋 Все пакеты"), id="plan_pkg_list")
                yield Button("🔐 Настроить .env [E]", variant="warning", id="btn_edit_pkg_env", disabled=True)

            with Vertical(id="center_column"):
                yield Label(
                    "Управление: Пробел — выбор пакета, Вправо/Влево — раскрыть/свернуть (Вправо на ENV — настройка .env)"
                )
                yield InfrastructureTree(self.engine, self, id="packages_tree")
                yield Label("📋 Предпросмотр плана: Все пакеты", id="lbl_plan_title")
                yield PlanPreviewLog(self.engine, self, id="preview_log")

            with Vertical(id="right_sidebar"):
                with Vertical(id="settings_box"):
                    yield Label("⚙️ Настройки", classes="sidebar_title")
                    yield Checkbox("🛡️ Sandbox (песочница)", value=is_sb, id="chk_sandbox")
                    yield Label("Система песочницы:", id="lbl_sandbox_os")
                    yield Select(
                        self.SANDBOX_OS_OPTIONS,
                        value=initial_os,
                        allow_blank=False,
                        id="sel_sandbox_os",
                    )
                    yield Label("📁 Предустановки .env:\ndeploy-engine/env/", id="lbl_env_dir_hint")

                with Vertical(id="action_buttons_box"):
                    yield Button("Выполнить план", variant="success", id="btn_run")
                    yield Button("Выход", variant="error", id="btn_exit")
        yield Footer()

    def on_mount(self) -> None:
        self.render_live_preview()
        self.query_one("#packages_tree", InfrastructureTree).focus()

    def _find_package_env_unit(self, pkg_key: Optional[str]) -> Optional[Tuple[str, str, str, str]]:
        """Ищет .env юнит у пакета и возвращает (pkg_name, unit_name, src_path, dest_path)."""
        if not pkg_key or not self.engine.registry.has(pkg_key):
            return None
        pkg = self.engine.registry.get(pkg_key)
        pkg_name = pkg.get("name", pkg_key.split("/")[-1])
        for u_name, u_spec in sorted((pkg.get("units") or {}).items()):
            u_spec = u_spec or {}
            u_type = u_spec.get("type")
            if u_type == "env" or u_name.endswith(".env") or u_name == "deploy.env":
                try:
                    src_path, dest_path, _, _ = self.engine.get_paths_and_modes(f"{pkg_name}:{u_name}")
                    if os.path.isfile(src_path):
                        return pkg_name, u_name, src_path, dest_path
                except Exception:
                    continue
        return None

    def _resolve_active_env_target(self) -> Optional[Tuple[str, str, str, str]]:
        """Возвращает .env юнит для выбранной вкладки пакета слева."""
        if not self.selected_filter_pkg:
            return None
        return self._find_package_env_unit(self.selected_filter_pkg)

    def _update_env_button_state(self) -> None:
        """Обновляет заголовок плана и активирует кнопку .env при выборе вкладки пакета."""
        title_lbl = self.query_one("#lbl_plan_title", Label)
        env_btn = self.query_one("#btn_edit_pkg_env", Button)

        scope_text = self.selected_filter_pkg if self.selected_filter_pkg else "Все пакеты"
        title_lbl.update(f"📋 Предпросмотр плана: {scope_text}")

        env_target = self._resolve_active_env_target()
        if env_target:
            pkg_name, _, _, _ = env_target
            preset_exists = os.path.isfile(self.engine.env_manager.get_local_preset_path(pkg_name))
            mark = "✓ " if preset_exists else ""
            env_btn.label = f"🔐 {mark}Настроить .env [E]"
            env_btn.disabled = False
        else:
            env_btn.label = "🔐 Настроить .env [E]"
            env_btn.disabled = True

    def _sync_plan_tabs(self) -> None:
        """Обновляет вертикальный список вкладок выбранных пакетов слева на всю высоту."""
        opt_list = self.query_one("#plan_pkg_list", OptionList)
        active_pkgs = sorted(
            [
                k
                for k, v in self.actions.items()
                if v in ("install", "reinstall", "uninstall")
                and self.engine.registry.has(k)
                and self.engine.is_package_compatible(k)
            ]
        )

        current_sig = tuple((k, self.actions.get(k, "")) for k in active_pkgs)
        if current_sig == self._last_tabs_sig:
            return
        self._last_tabs_sig = current_sig

        if self.selected_filter_pkg not in active_pkgs:
            self.selected_filter_pkg = None

        icons = {
            "install": "[bold green]+[/bold green]",
            "reinstall": "[bold yellow]↻[/bold yellow]",
            "uninstall": "[bold red]-[/bold red]",
        }
        all_title = f"📋 Все пакеты ({len(active_pkgs)})" if active_pkgs else "📋 Все пакеты"

        opt_list.clear_options()
        opt_list.add_option(Option(all_title))
        new_map: List[Optional[str]] = [None]

        selected_idx = 0
        for idx, pkg_key in enumerate(active_pkgs, start=1):
            act = self.actions.get(pkg_key, "install")
            icon = icons.get(act, "📦")
            opt_list.add_option(Option(f"{icon} {pkg_key}"))
            new_map.append(pkg_key)
            if pkg_key == self.selected_filter_pkg:
                selected_idx = idx

        self.option_pkg_map = new_map
        opt_list.highlighted = selected_idx

    def render_live_preview(self) -> None:
        """Обновляет список вкладок слева, кнопку .env и рендерит план в RichLog."""
        self._sync_plan_tabs()
        self._update_env_button_state()
        log_widget = self.query_one("#preview_log", PlanPreviewLog)
        log_widget.update_plan_view(filter_pkg=self.selected_filter_pkg)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "plan_pkg_list":
            idx = event.option_index
            if 0 <= idx < len(self.option_pkg_map):
                self.selected_filter_pkg = self.option_pkg_map[idx]
                self._update_env_button_state()
                self.query_one("#preview_log", PlanPreviewLog).update_plan_view(filter_pkg=self.selected_filter_pkg)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "plan_pkg_list":
            idx = event.option_index
            if 0 <= idx < len(self.option_pkg_map):
                self.selected_filter_pkg = self.option_pkg_map[idx]
                self._update_env_button_state()
                self.query_one("#preview_log", PlanPreviewLog).update_plan_view(filter_pkg=self.selected_filter_pkg)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        node = event.node
        if node and node.data:
            if node.data.get("is_package"):
                self.cursor_pkg_key = node.data.get("key")
            elif node.data.get("pkg_name"):
                self.cursor_pkg_key = node.data.get("pkg_name")
            else:
                self.cursor_pkg_key = None
            self._update_env_button_state()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "chk_sandbox":
            sel = self.query_one("#sel_sandbox_os", Select)
            self._apply_sandbox_settings(event.value, str(sel.value))

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "sel_sandbox_os":
            chk = self.query_one("#chk_sandbox", Checkbox)
            if chk.value:
                self._apply_sandbox_settings(True, str(event.value))

    def _apply_sandbox_settings(self, sandbox_enabled: bool, sandbox_os: str) -> None:
        self.engine.configure_environment(sandbox=sandbox_enabled, sandbox_os=sandbox_os)
        self._last_tabs_sig = None
        tree = self.query_one("#packages_tree", InfrastructureTree)
        tree.rebuild_tree()
        self.render_live_preview()

    def _launch_env_modal(self, pkg_name: str, unit_name: str, src_path: str, dest_path: str) -> None:
        def _on_modal_closed(saved_preset_path: Optional[str]) -> None:
            if saved_preset_path:
                tree = self.query_one("#packages_tree", InfrastructureTree)
                tree.mark_env_configured(pkg_name)
                self.render_live_preview()

        self.push_screen(
            EnvEditorModal(self.engine, pkg_name, unit_name, src_path, dest_path),
            _on_modal_closed,
        )

    def open_env_editor(self, env_node: TreeNode) -> None:
        """Открывает модальное окно редактирования .env из узла ENV в дереве."""
        if not env_node.data:
            return
        pkg_name = env_node.data.get("pkg_name", "")
        unit_name = env_node.data.get("unit_name", "deploy.env")
        try:
            src_path, dest_path, _, _ = self.engine.get_paths_and_modes(f"{pkg_name}:{unit_name}")
        except Exception:
            return
        if os.path.isfile(src_path):
            self._launch_env_modal(pkg_name, unit_name, src_path, dest_path)

    def action_edit_current_env(self) -> None:
        """Горячая клавиша E / кнопка быстрой настройки .env для выбранного во вкладке пакета."""
        target = self._resolve_active_env_target()
        if target:
            self._launch_env_modal(*target)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_exit":
            self.exit()
        elif event.button.id == "btn_edit_pkg_env":
            self.action_edit_current_env()
        elif event.button.id == "btn_run":
            active_targets = {
                k: v
                for k, v in self.actions.items()
                if v != "none" and self.engine.registry.has(k) and self.engine.is_package_compatible(k)
            }
            if not active_targets:
                self.query_one("#preview_log", PlanPreviewLog).write(
                    "[bold red]❌ План пуст! Выберите пакеты клавишей ПРОБЕЛ перед выполнением.[/bold red]"
                )
                return
            self.exit(active_targets)

