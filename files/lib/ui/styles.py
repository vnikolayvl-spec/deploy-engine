#!/usr/bin/env python3
"""
Глобальные стили CSS для трехколоночного TUI-интерфейса Deploy Engine.
- Левая колонка: вкладки выбранных пакетов на всю высоту.
- Центральная колонка: дерево пакетов сверху и предпросмотр плана снизу.
- Правая колонка: настройки Sandbox сверху и кнопки «Выполнить план» / «Выход» внизу.
"""

APP_CSS = """
Screen {
    align: center middle;
}
#main_layout {
    width: 98%;
    height: 96%;
    border: solid $primary;
    background: $panel;
    padding: 0 1;
}
#left_sidebar {
    width: 30;
    height: 100%;
    border-right: solid $primary-darken-1;
    padding: 1 1 1 0;
}
#center_column {
    width: 1fr;
    height: 100%;
    padding: 1;
}
#right_sidebar {
    width: 34;
    height: 100%;
    border-left: solid $primary-darken-1;
    padding: 1 0 1 1;
}
.sidebar_title {
    color: $accent;
    text-style: bold;
    margin-bottom: 1;
}
#plan_pkg_list {
    height: 1fr;
    border: round $secondary;
    background: $surface;
    margin-bottom: 1;
}
#btn_edit_pkg_env {
    width: 100%;
    height: 3;
    margin: 0;
}
InfrastructureTree {
    height: 1fr;
    border: round $accent;
    margin-bottom: 1;
    background: $surface;
}
#lbl_plan_title {
    text-style: bold;
    color: $text;
    margin: 0 0 1 0;
}
PlanPreviewLog {
    height: 1fr;
    border: solid $secondary;
    background: $surface;
}
#settings_box {
    height: 1fr;
    border: round $primary-darken-2;
    background: $surface;
    padding: 1;
}
#chk_sandbox {
    margin-bottom: 1;
}
#lbl_sandbox_os {
    margin: 1 0 0 0;
}
#sel_sandbox_os {
    width: 100%;
    margin-bottom: 1;
}
#lbl_env_dir_hint {
    color: $text-muted;
    margin-top: 1;
}
#action_buttons_box {
    height: auto;
    padding-top: 1;
    align: center bottom;
}
#btn_run {
    width: 100%;
    margin-bottom: 1;
}
#btn_exit {
    width: 100%;
}
EnvEditorModal {
    align: center middle;
}
#env_modal_dialog {
    width: 80%;
    height: 80%;
    border: thick $accent;
    background: $panel;
    padding: 1 2;
}
#env_modal_title {
    color: $accent;
    text-style: bold;
    margin-bottom: 0;
}
#env_modal_subtitle {
    color: $text-muted;
    margin-bottom: 1;
}
#env_modal_scroll {
    height: 1fr;
    border: solid $primary-darken-1;
    background: $surface;
    padding: 0 1;
    margin-bottom: 1;
}
.env_compact_row {
    height: auto;
    min-height: 1;
    margin-bottom: 0;
    padding: 0;
    align: left middle;
}
.env_compact_label {
    width: 52%;
    height: auto;
    color: $text;
    padding-right: 1;
}
.env_compact_label_req {
    width: 52%;
    height: auto;
    color: $warning;
    text-style: bold;
    padding-right: 1;
}
.env_compact_input {
    width: 48%;
    height: 1;
    border: none;
    background: $panel;
    padding: 0 1;
    margin: 0 0 1 0;
}
.env_collapsed_bar {
    height: 3;
    border: solid $success;
    background: $surface;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}
.env_collapsed_label {
    width: 1fr;
    color: $success;
}
.btn_env_compact {
    min-width: 18;
    height: 1;
    border: none;
}
.env_inline_editor {
    height: 1fr;
    border: solid $warning;
    background: $surface;
    padding: 1;
    margin-bottom: 1;
}
.env_inline_title {
    color: $accent;
    text-style: bold;
    margin-bottom: 1;
}
.env_inline_scroll {
    height: 1fr;
    padding: 0 1;
}
.env_inline_footer {
    height: auto;
    padding-top: 1;
    align: right middle;
}
.env_inline_status {
    width: 1fr;
    color: $warning;
}
#env_modal_buttons {
    height: auto;
    align: center middle;
}
PackageDetailsModal, ExecutionModal {
    align: center middle;
}
#pkg_modal_dialog, #exec_modal_dialog {
    width: 90%;
    height: 88%;
    border: thick $accent;
    background: $panel;
    padding: 1 2;
}
#pkg_modal_title, #exec_modal_title {
    color: $accent;
    text-style: bold;
    margin-bottom: 0;
}
#exec_modal_status {
    color: $text-muted;
    margin-bottom: 1;
}
#pkg_modal_tabs, #exec_modal_tabs {
    height: auto;
    margin-bottom: 1;
}
#pkg_modal_tabs Button, #exec_modal_tabs Button {
    margin-right: 1;
}
#exec_panes_container {
    height: 1fr;
    margin-bottom: 1;
}
.exec_pkg_pane {
    height: 1fr;
    display: none;
}
#pkg_details_log, #exec_modal_log, .exec_pkg_log {
    height: 1fr;
    border: solid $primary-darken-1;
    background: $surface;
    padding: 1;
    margin-bottom: 0;
}
#pkg_modal_actions, #exec_modal_buttons {
    height: auto;
    align: center middle;
}
#pkg_modal_actions Button {
    margin-right: 1;
}
"""
