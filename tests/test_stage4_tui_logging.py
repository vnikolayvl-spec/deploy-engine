"""
Unit tests for Stage 4 TUI improvements:
- [HH:MM:SS] timestamps on every log line in ExecutionModal
- Clearing all log widgets (general + package tabs) on new installation mount
- Non-blocking animated Braille spinner + elapsed time [MM:SS] + live phase updates during system updates
"""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from types import ModuleType, SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files"))

from lib.core.engine import Engine
from lib.core.execution_context import ExecutionContext
from lib.providers.linux_provider import LinuxProvider
from lib.providers.sandbox_provider import SandboxProvider
from lib.ui.activity_indicator import ActivityIndicator


class TestStage4TuiLogging(unittest.TestCase):
    """Тесты Этапа 4: время в логах TUI, очистка логов при новой установке и индикатор активности."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="de_stage4_test_")
        self.repo_dir = os.path.join(self.test_dir, "repo")
        self.sb_dir = os.path.join(self.test_dir, "sandbox")
        os.makedirs(self.repo_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _ensure_textual_stub(self):
        try:
            import textual  # noqa: F401
        except ImportError:
            class _Meta(type):
                def __getattr__(cls, _name): return object

            class _Dummy(metaclass=_Meta):
                def __init__(self, *a, **kw): pass

            for mod_name, attrs in {
                "textual": {}, "textual.app": {"App": _Dummy, "ComposeResult": object},
                "textual.containers": {"Horizontal": _Dummy, "Vertical": _Dummy, "VerticalScroll": _Dummy},
                "textual.screen": {"ModalScreen": _Dummy},
                "textual.widgets": {"Button": _Dummy, "ContentSwitcher": _Dummy, "Input": _Dummy, "Label": _Dummy, "RichLog": _Dummy},
            }.items():
                m = ModuleType(mod_name)
                for k, v in attrs.items(): setattr(m, k, v)
                sys.modules[mod_name] = m

    def _create_pkg(self, name: str) -> None:
        pkg_dir = os.path.join(self.repo_dir, name)
        os.makedirs(os.path.join(pkg_dir, "files"), exist_ok=True)
        with open(os.path.join(pkg_dir, "files", "run.sh"), "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho ok\n")
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": name,
                    "version": "1.0.0",
                    "units": {"run.sh": {"src": "files/run.sh", "dest": "{{SYS_BIN}}/run.sh", "type": "script"}},
                },
                f,
            )

    def test_activity_indicator_timestamps_spinner_and_pause(self):
        """ActivityIndicator форматирует [HH:MM:SS] без дублирования, крутит спиннер и считает [MM:SS]."""
        fixed_dt = datetime(2026, 11, 21, 9, 5, 42)
        stamped = ActivityIndicator.format_log_line("Обновление кэша apt...", now_dt=fixed_dt)
        self.assertEqual(stamped, "[09:05:42] Обновление кэша apt...")
        # Повторное форматирование не дублирует время
        self.assertEqual(ActivityIndicator.format_log_line(stamped, now_dt=fixed_dt), stamped)
        self.assertEqual(ActivityIndicator.format_log_line("   ", now_dt=fixed_dt), "")

        ind = ActivityIndicator()
        ind.started_at = 100.0
        ind.set_phase("Обновление индекса пакетов (apt-get)...")
        s1 = ind.render_status(advance=True, now_monotonic=115.0)
        s2 = ind.render_status(advance=True, now_monotonic=165.0)
        self.assertEqual(s1, "⠋ Обновление индекса пакетов (apt-get)... [00:15]")
        self.assertEqual(s2, "⠙ Обновление индекса пакетов (apt-get)... [01:05]")

        # При паузе (ожидание .env) выводится сообщение паузы, после resume — снова спиннер
        ind.pause("⏸ Подтвердите .env...")
        self.assertEqual(ind.render_status(advance=True, now_monotonic=170.0), "⏸ Подтвердите .env...")
        ind.resume()
        self.assertIn("[01:10]", ind.render_status(advance=True, now_monotonic=170.0))

        # Все кадры спиннера без U+FE0F
        for frame in ActivityIndicator.SPINNER_FRAMES:
            self.assertNotIn("\ufe0f", frame)

    def test_execution_modal_writes_timestamps_clears_logs_and_ticks_spinner(self):
        """ExecutionModal добавляет [HH:MM:SS] в общий и пакетный лог, очищает логи при старте и крутит спиннер."""
        self._ensure_textual_stub()
        from lib.ui.execution_modal import ExecutionModal

        self._create_pkg("alpha-pkg")
        ctx = ExecutionContext(non_interactive=True, sandbox=True)
        provider = SandboxProvider(ctx, sandbox_dir=self.sb_dir, target_os="debian")
        engine = Engine(ctx, provider=provider)
        engine.discover_packages(search_roots=[self.repo_dir], force_rescan=True)

        modal = ExecutionModal(engine, {"alpha-pkg": "install"})
        gen_lines = ["stale old log"]
        pkg_lines = ["stale pkg log"]
        status_updates = []
        close_btn = SimpleNamespace(label="", variant="primary", disabled=True, focus=lambda: None)
        gen_log = SimpleNamespace(write=gen_lines.append, clear=gen_lines.clear, display=True)
        pkg_log = SimpleNamespace(write=pkg_lines.append, clear=pkg_lines.clear, display=True)
        status_lbl = SimpleNamespace(update=status_updates.append)

        switcher = SimpleNamespace(current="exec_modal_log")
        tab_gen = SimpleNamespace(variant="primary")
        tab_pkg = SimpleNamespace(label="", variant="default")

        def _query(selector, *_a):
            if selector == "#exec_panes_container": return switcher
            if selector == "#tab_btn___general__": return tab_gen
            if selector == "#tab_btn_alpha-pkg": return tab_pkg
            if selector == "#exec_modal_log": return gen_log
            if selector == "#exec_log_alpha-pkg": return pkg_log
            if selector == "#exec_modal_status": return status_lbl
            if selector == "#btn_exec_close": return close_btn
            return SimpleNamespace(label="", variant="default", display=True, update=lambda *_x: None)

        modal.query_one = _query
        type(modal).is_mounted = property(lambda _s: True)

        # 1. Очистка логов перед новой установкой
        modal.clear_all_logs()
        self.assertEqual(gen_lines, [])
        self.assertEqual(pkg_lines, [])

        # 2. Каждая строка лога получает префикс [HH:MM:SS]
        modal._write_line("alpha-pkg", "Запуск установки\nГотово")
        self.assertEqual(len(gen_lines), 2)
        self.assertEqual(len(pkg_lines), 2)
        for line in gen_lines + pkg_lines:
            self.assertRegex(line, r"^\[\d{2}:\d{2}:\d{2}\] ")

        # 3. Переключение вкладок через ContentSwitcher гарантирует отображение ровно одной панели
        modal._switch_active_tab("alpha-pkg")
        self.assertEqual(switcher.current, "exec_pane_alpha-pkg")
        self.assertEqual(tab_pkg.variant, "primary")
        self.assertEqual(tab_gen.variant, "default")
        modal._switch_active_tab("__general__")
        self.assertEqual(switcher.current, "exec_modal_log")
        self.assertEqual(tab_gen.variant, "primary")
        self.assertEqual(tab_pkg.variant, "default")

        # 4. Обновление фазы и тик спиннера обновляют статус и кнопку
        modal.indicator.set_phase("Обновление индекса пакетов (apt-get)...")
        modal._tick_activity_indicator()
        self.assertTrue(status_updates)
        self.assertIn("Обновление индекса пакетов (apt-get)...", status_updates[-1])
        self.assertIn("Выполняется [", close_btn.label)

    def test_linux_provider_emits_phases_during_apt_update_and_install(self):
        """LinuxProvider транслирует фазы обновления индекса и установки системных пакетов в ExecutionContext."""
        ctx = ExecutionContext(non_interactive=True)
        phases = []
        ctx.add_phase_listener(phases.append)
        lp = LinuxProvider(ctx)

        with mock.patch.object(lp, "detect_package_manager", return_value="apt-get"):
            with mock.patch.object(lp, "needs_cache_update", return_value=True):
                with mock.patch.object(lp, "_touch_stamp"):
                    with mock.patch.object(ctx, "run_logged_subprocess", return_value=0) as run_mock:
                        ok = lp.install_sys_packages(["curl", "git"])

        self.assertTrue(ok)
        self.assertTrue(any("Обновление индекса пакетов (apt-get)" in p for p in phases))
        self.assertTrue(any("Установка системных пакетов (apt-get: curl, git)" in p for p in phases))
        # Проверка неинтерактивного DEBIAN_FRONTEND для apt-get
        for call in run_mock.call_args_list:
            self.assertEqual(call.kwargs.get("env", {}).get("DEBIAN_FRONTEND"), "noninteractive")


if __name__ == "__main__":
    unittest.main()
