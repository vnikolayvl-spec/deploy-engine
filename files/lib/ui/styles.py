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
    padding: 1;
    margin-bottom: 1;
}
.env_field_label {
    margin-top: 1;
    margin-bottom: 0;
    color: $text;
}
.env_field_input {
    margin-bottom: 1;
}
#env_modal_buttons {
    height: auto;
    align: center middle;
}
"""
