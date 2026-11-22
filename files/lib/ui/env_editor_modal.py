#!/usr/bin/env python3
"""
Модальное окно редактирования всех переменных окружения (.env) пакета в TUI.
Сохраняет пресеты во внутреннее хранилище (<LOCAL_ENV_DIR>/<pkg>.env), не изменяя файлы в репозитории.
Для уже установленного пакета предлагает дополнительно применить изменения в системный .env.
"""
import os
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
        self.can_apply_system = self._detect_installed_or_system_env()
        self.entries: List[Dict] = self.engine.env_manager.parser.parse_editable_entries(
            self.src_path,
            override_paths=[self.dest_path, self.preset_path],
        )

    def _detect_installed_or_system_env(self) -> bool:
        """Возвращает True, если пакет уже установлен или системный .env уже существует."""
        if getattr(self.engine, "state_repo", None) and self.engine.state_repo.get_installed_package(self.pkg_name):
            return True
        try:
            return bool(self.dest_path and os.path.isfile(self.dest_path))
        except PermissionError:
            return True
        except OSError:
            return False

    def compose(self) -> ComposeResult:
        with Vertical(id="env_modal_dialog"):
            yield Label(
                f"🔐 Настройка переменных окружения: {self.pkg_name} ({self.unit_name})",
                id="env_modal_title",
            )
            subtitle = f"📁 Внутренний пресет: {self.preset_path} (репозиторий не изменяется)"
            if self.can_apply_system:
                subtitle += f"\n🔐 Системный .env: {self.dest_path}"
            yield Label(subtitle, id="env_modal_subtitle")
            with VerticalScroll(id="env_modal_scroll"):
                if not self.entries:
                    yield Label("В файле .env не обнаружено переменных для настройки.")
                for idx, entry in enumerate(self.entries):
                    key = entry["key"]
                    req = entry.get("required_prompt", False)
                    has_p = entry.get("has_prompt", False)
                    is_auto = entry.get("is_auto", False)
                    notice = entry.get("notice") or ""
                    badge = " [❗ ОБЯЗАТЕЛЬНО]" if req else (" [АВТО]" if is_auto else (" [PROMPT]" if has_p else ""))
                    desc_text = f" ({notice})" if notice else ""
                    with Horizontal(classes="env_compact_row"):
                        yield Label(
                            f"{key}{badge}{desc_text}",
                            classes="env_compact_label_req" if req else "env_compact_label",
                        )
                        yield Input(
                            value=str(entry.get("value", "")),
                            placeholder=str("#AUTO# — автоопределение" if is_auto else (entry.get("default_value") or notice or "Введите значение...")),
                            id=f"env_input_{idx}",
                            classes="env_compact_input",
                        )
            with Horizontal(id="env_modal_buttons"):
                yield Button("💾 Сохранить пресет", variant="success", id="btn_env_save")
                if self.can_apply_system:
                    yield Button("🚀 Сохранить и применить в системный .env", variant="primary", id="btn_env_save_apply")
                yield Button("Отмена (Esc)", variant="default", id="btn_env_cancel")

    def on_mount(self) -> None:
        self._validate_required_inputs()

    def _collect_values(self) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for idx, entry in enumerate(self.entries):
            inp = self.query_one(f"#env_input_{idx}", Input)
            values[entry["key"]] = inp.value.strip()
        return values

    def _validate_required_inputs(self) -> bool:
        if not self.is_mounted:
            return True
        missing = False
        for idx, entry in enumerate(self.entries):
            if entry.get("required_prompt"):
                inp = self.query_one(f"#env_input_{idx}", Input)
                if not inp.value.strip():
                    missing = True
                    break
        self.query_one("#btn_env_save", Button).disabled = missing
        if self.can_apply_system:
            try:
                self.query_one("#btn_env_save_apply", Button).disabled = missing
            except Exception:
                pass
        return not missing

    def on_input_changed(self, _event: Input.Changed) -> None:
        self._validate_required_inputs()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_env_cancel":
            self.dismiss(None)
        elif event.button.id == "btn_env_save":
            if not self._validate_required_inputs():
                return
            saved_path = self.engine.env_manager.save_local_preset(self.pkg_name, self.src_path, self._collect_values())
            self.dismiss({"preset_path": saved_path, "applied_system": False, "warning": None})
        elif event.button.id == "btn_env_save_apply":
            if not self._validate_required_inputs():
                return
            saved_path, warn = self.engine.env_manager.apply_preset_to_system_env(
                self.pkg_name, self.src_path, self.dest_path, self._collect_values()
            )
            self.dismiss({"preset_path": saved_path, "applied_system": warn is None, "warning": warn})
