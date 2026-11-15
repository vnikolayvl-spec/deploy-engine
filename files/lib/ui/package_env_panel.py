#!/usr/bin/env python3
"""
Компактная панель редактирования и подтверждения переменных .env на вкладке пакета в ExecutionModal.
До подтверждения перекрывает лог пакета, а после подтверждения сворачивается/скрывается, открывая лог.
"""
import os
import re
import threading
from typing import Callable, Dict, List, Optional
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label


class PackageEnvPanel(Vertical):
    """Встраиваемая панель настройки и подтверждения .env для вкладки пакета в окне выполнения."""

    def __init__(
        self,
        engine,
        pkg_name: str,
        unit_name: str,
        src_path: str,
        dest_path: str,
        on_state_change: Optional[Callable[[str, bool, bool], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.engine = engine
        self.pkg_name = pkg_name
        self.unit_name = unit_name
        self.src_path = src_path
        self.dest_path = dest_path
        self.on_state_change = on_state_change
        self.safe_pkg = re.sub(r"[^a-zA-Z0-9_-]", "_", pkg_name)
        self.preset_path = self.engine.env_manager.get_local_preset_path(pkg_name)
        self.entries: List[Dict] = self.engine.env_manager.parser.parse_editable_entries(
            self.src_path,
            override_paths=[self.dest_path, self.preset_path],
        )
        self.approved_values: Dict[str, str] = {
            e["key"]: str(e.get("value", "")) for e in self.entries
        }
        self.approval_event = threading.Event()
        self.locked = False

        preset_exists = os.path.isfile(self.preset_path)
        missing_req = self._has_missing_required(self.approved_values)
        self.approved = bool(preset_exists and not missing_req)
        if self.approved:
            self.approval_event.set()

    def _has_missing_required(self, values_map: Dict[str, str]) -> bool:
        """Возвращает True, если хотя бы один промпт без значения по умолчанию не заполнен."""
        for entry in self.entries:
            if entry.get("required_prompt"):
                val = str(values_map.get(entry["key"], "")).strip()
                if not val:
                    return True
        return False

    def has_missing_required_now(self) -> bool:
        return self._has_missing_required(self._collect_current_values())

    def compose(self) -> ComposeResult:
        with Horizontal(id=f"env_collapsed_{self.safe_pkg}", classes="env_collapsed_bar"):
            yield Label(
                f"✅ .env подтвержден ({self.preset_path})",
                id=f"env_collapsed_lbl_{self.safe_pkg}",
                classes="env_collapsed_label",
            )
            yield Button(
                "🔧 Изменить .env",
                variant="default",
                id=f"btn_env_reopen_{self.safe_pkg}",
                classes="btn_env_compact",
            )

        with Vertical(id=f"env_editor_box_{self.safe_pkg}", classes="env_inline_editor"):
            yield Label(
                f"🔐 Настройка переменных окружения: {self.pkg_name} ({self.unit_name})",
                classes="env_inline_title",
            )
            with VerticalScroll(id=f"env_scroll_{self.safe_pkg}", classes="env_inline_scroll"):
                for idx, entry in enumerate(self.entries):
                    key = entry["key"]
                    req = entry.get("required_prompt", False)
                    has_p = entry.get("has_prompt", False)
                    notice = entry.get("notice") or ""
                    badge = " [❗ ОБЯЗАТЕЛЬНО]" if req else (" [PROMPT]" if has_p else "")
                    hint = f" ({notice})" if notice else ""
                    with Horizontal(classes="env_compact_row"):
                        yield Label(
                            f"{key}{badge}{hint}",
                            classes="env_compact_label_req" if req else "env_compact_label",
                        )
                        yield Input(
                            value=str(entry.get("value", "")),
                            placeholder=str(entry.get("default_value") or notice or "Введите значение..."),
                            id=f"pkg_env_inp_{self.safe_pkg}_{idx}",
                            classes="env_compact_input",
                        )
            with Horizontal(classes="env_inline_footer"):
                yield Label("", id=f"env_status_lbl_{self.safe_pkg}", classes="env_inline_status")
                yield Button(
                    "✅ Принять .env",
                    variant="success",
                    id=f"btn_env_approve_{self.safe_pkg}",
                )

    def on_mount(self) -> None:
        self._sync_visibility_and_validation()

    def _collect_current_values(self) -> Dict[str, str]:
        values: Dict[str, str] = dict(self.approved_values)
        if not self.is_mounted:
            return values
        for idx, entry in enumerate(self.entries):
            try:
                inp = self.query_one(f"#pkg_env_inp_{self.safe_pkg}_{idx}", Input)
                values[entry["key"]] = inp.value.strip()
            except Exception:
                pass
        return values

    def _sync_visibility_and_validation(self) -> None:
        if not self.is_mounted:
            return
        collapsed_bar = self.query_one(f"#env_collapsed_{self.safe_pkg}", Horizontal)
        editor_box = self.query_one(f"#env_editor_box_{self.safe_pkg}", Vertical)
        approve_btn = self.query_one(f"#btn_env_approve_{self.safe_pkg}", Button)
        status_lbl = self.query_one(f"#env_status_lbl_{self.safe_pkg}", Label)

        cur_vals = self._collect_current_values()
        missing_req = self._has_missing_required(cur_vals)
        approve_btn.disabled = missing_req

        if missing_req:
            status_lbl.update("❗ Заполните все поля [❗ ОБЯЗАТЕЛЬНО] без дефолта для продолжения")
        else:
            status_lbl.update("💡 Проверьте значения и нажмите «Принять .env»")

        if self.locked:
            self.display = False
        elif self.approved:
            self.display = True
            self.styles.height = "auto"
            collapsed_bar.display = True
            editor_box.display = False
        else:
            self.display = True
            self.styles.height = "1fr"
            collapsed_bar.display = False
            editor_box.display = True

        if callable(self.on_state_change):
            self.on_state_change(self.pkg_name, self.approved, missing_req)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id and event.input.id.startswith(f"pkg_env_inp_{self.safe_pkg}_"):
            self._sync_visibility_and_validation()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == f"btn_env_approve_{self.safe_pkg}":
            cur_vals = self._collect_current_values()
            if self._has_missing_required(cur_vals):
                return
            self.approved_values = cur_vals
            self.engine.env_manager.save_local_preset(self.pkg_name, self.src_path, cur_vals)
            self.approved = True
            self.approval_event.set()
            self._sync_visibility_and_validation()
        elif btn_id == f"btn_env_reopen_{self.safe_pkg}" and not self.locked:
            self.approved = False
            self.approval_event.clear()
            self._sync_visibility_and_validation()
            self.focus_first_input()

    def focus_first_input(self) -> None:
        """Устанавливает фокус на первое незаполненное обязательное поле или кнопку принятия."""
        if not self.is_mounted or self.approved:
            return
        for idx, entry in enumerate(self.entries):
            try:
                inp = self.query_one(f"#pkg_env_inp_{self.safe_pkg}_{idx}", Input)
                if entry.get("required_prompt") and not inp.value.strip():
                    inp.focus()
                    return
            except Exception:
                pass
        try:
            self.query_one(f"#btn_env_approve_{self.safe_pkg}", Button).focus()
        except Exception:
            pass

    def lock_after_install(self) -> None:
        """Скрывает панель .env после завершения шага конфигурации ENV пакета, отдавая всё место логу."""
        self.locked = True
        self.approved = True
        self.approval_event.set()
        if self.is_mounted:
            self._sync_visibility_and_validation()
