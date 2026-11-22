"""
lib/ui/activity_indicator.py: Неблокирующий индикатор активности (спиннер + таймер) и форматирование времени логов TUI.
Использует только символы Брайля (ширина 1, без U+FE0F), чтобы не ломать рамки терминала macOS/Linux.
"""
import re
import time
from datetime import datetime
from typing import Optional


class ActivityIndicator:
    """Управляет анимацией спиннера, счетчиком времени выполнения и префиксом [HH:MM:SS] для строк лога."""

    SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
    TIMESTAMP_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s")

    def __init__(self, default_phase: str = "Операция выполняется, пожалуйста подождите..."):
        self.default_phase = default_phase
        self.current_phase = default_phase
        self.paused_message: Optional[str] = None
        self.frame_idx = 0
        self.started_at = time.monotonic()

    def reset(self, phase: Optional[str] = None) -> None:
        """Сбрасывает таймер и индекс анимации при старте новой операции."""
        self.started_at = time.monotonic()
        self.frame_idx = 0
        self.paused_message = None
        self.current_phase = phase or self.default_phase

    def set_phase(self, phase: str) -> None:
        """Обновляет описание текущего этапа (например, обновление кэша apt или установка пакетов)."""
        cleaned = (phase or "").strip()
        self.current_phase = cleaned if cleaned else self.default_phase

    def pause(self, message: str) -> None:
        """Приостанавливает спиннер на время ожидания действий пользователя (например, подтверждения .env)."""
        self.paused_message = message

    def resume(self, phase: Optional[str] = None) -> None:
        """Возобновляет спиннер после подтверждения пользователя."""
        self.paused_message = None
        if phase is not None:
            self.set_phase(phase)

    def format_elapsed(self, now_monotonic: Optional[float] = None) -> str:
        """Возвращает прошедшее время в формате MM:SS."""
        now = time.monotonic() if now_monotonic is None else now_monotonic
        total_sec = max(0, int(now - self.started_at))
        mins, secs = divmod(total_sec, 60)
        return f"{mins:02d}:{secs:02d}"

    def next_frame(self) -> str:
        """Возвращает текущий кадр спиннера и переходит к следующему."""
        frame = self.SPINNER_FRAMES[self.frame_idx % len(self.SPINNER_FRAMES)]
        self.frame_idx = (self.frame_idx + 1) % len(self.SPINNER_FRAMES)
        return frame

    def render_status(self, advance: bool = True, now_monotonic: Optional[float] = None) -> str:
        """Формирует строку статуса: сообщение паузы или '<спиннер> <этап> [MM:SS]'."""
        if self.paused_message:
            return self.paused_message
        frame = self.next_frame() if advance else self.SPINNER_FRAMES[self.frame_idx % len(self.SPINNER_FRAMES)]
        elapsed = self.format_elapsed(now_monotonic=now_monotonic)
        return f"{frame} {self.current_phase} [{elapsed}]"

    @classmethod
    def format_log_line(cls, line: str, now_dt: Optional[datetime] = None) -> str:
        """Добавляет временную метку [HH:MM:SS] в начало строки лога (без дублирования)."""
        text = str(line)
        if not text.strip():
            return ""
        if cls.TIMESTAMP_RE.match(text):
            return text
        ts = (now_dt or datetime.now()).strftime("%H:%M:%S")
        return f"[{ts}] {text}"
