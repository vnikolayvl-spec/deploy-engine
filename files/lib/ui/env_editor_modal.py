#!/usr/bin/env python3
"""
Модальное окно редактирования всех переменных окружения (.env) пакета в TUI.
Сохраняет предустановки в локальную папку ./env/<pkg>.env, не изменяя репозиторий пакетов.
"""
from typing import Dict, List
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class EnvEditorModal(ModalScreen):
    """Интерактивное модальное окно для заполнения переменных .env и промптов пакета."""

    BINDINGS = [
        ("escape", "cancel", "Отмена"),
    ]

    def __init__(self, engine, pkg_name: str, unit_name: str, src_path: str, dest_path: str):
        super().__init__()
        self.engine = engine
        self.pkg_name = pkg_name
        self.unit_name = unit_name
        self.src_path = src_path
        self.dest_path = dest_path
        self.preset_path = self.engine.env_manager.get_local_preset_path(pkg_name)
        self.entries: List[Dict] = self.engine.env_manager.parser.parse_editable_entries(
            self.src_path,
            override_paths=[self.dest_path, self.preset_path],
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="env_modal_dialog"):
            yield Label(
                f"🔐 Настройка переменных окружения: {self.pkg_name} ({self.unit_name})",
                id="env_modal_title",
            )
            yield Label(
                f"Предустановка сохраняется в: {self.preset_path} (исходный пакет не изменяется)",
                id="env_modal_subtitle",
            )
            with VerticalScroll(id="env_modal_scroll"):
                if not self.entries:
                    yield Label("В файле .env не обнаружено переменных для настройки.")
                for idx, entry in enumerate(self.entries):
                    key = entry["key"]
                    notice = entry.get("notice") or ""
                    badge = " [PROMPT]" if entry.get("has_prompt") else ""
                    desc_text = f" — {notice}" if notice else ""
                    yield Label(f"{key}{badge}{desc_text}", classes="env_field_label")
                    yield Input(
                        value=str(entry.get("value", "")),
                        placeholder=str(entry.get("default_value", "")),
                        id=f"env_input_{idx}",
                        classes="env_field_input",
                    )
            with Horizontal(id="env_modal_buttons"):
                yield Button("💾 Сохранить предустановку", variant="success", id="btn_env_save")
                yield Button("Отмена (Esc)", variant="default", id="btn_env_cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_env_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_env_save":
            values: Dict[str, str] = {}
            for idx, entry in enumerate(self.entries):
                inp = self.query_one(f"#env_input_{idx}", Input)
                values[entry["key"]] = inp.value.strip()
            saved_path = self.engine.env_manager.save_local_preset(
                self.pkg_name,
                self.src_path,
                values,
            )
            self.dismiss(saved_path)
