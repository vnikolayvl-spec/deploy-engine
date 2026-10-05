#!/usr/bin/env python3
"""
Главный диспетчер интерфейса (Screen Controller) Deploy Engine.
Монтирует изолированные компоненты стилей, дерева и логов Сводного Плана.
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, Button
from textual.containers import Vertical, Horizontal

# Импортируем наши новые изолированные компоненты интерфейса
from lib.ui.styles import APP_CSS
from lib.ui.package_tree import InfrastructureTree
from lib.ui.plan_preview import PlanPreviewLog

class DeployApp(App):
    TITLE = "Independent Multi-Action Deployer"
    CSS = APP_CSS  # Подключаем вынесенный модуль стилей

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        # Единая карта запланированных действий: имя_компонента -> действие
        self.actions = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main_container"):
            yield Label("Управление пакетами: Пробел — Циклическое переключение действий, Стрелки Право/Лево — Раскрыть/Свернуть")
            
            # Монтируем наш кастомный виджет дерева, передавая контекст self
            yield InfrastructureTree(self.engine, self, id="packages_tree")
            
            yield Label("Сводный план выполнения операций (Рендеринг на лету):")
            # Монтируем наш кастомный виджет логов, передавая контекст self
            yield PlanPreviewLog(self.engine, self, id="preview_log")
            
            with Horizontal():
                yield Button("Выполнить план", variant="success", id="btn_run")
                yield Button("Выход", variant="error", id="btn_exit")
        yield Footer()

    def render_live_preview(self) -> None:
        """Прокси-метод для вызова обновления внутри изолированного виджета логов"""
        log_widget = self.query_one("#preview_log")
        log_widget.update_plan_view()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Обработка нажатий главных кнопок приложения"""
        if event.button.id == "btn_exit":
            self.exit()
        elif event.button.id == "btn_run":
            # Фильтруем карту действий, исключая пустые "none", и возвращаем результат в стартер
            active_targets = {k: v for k, v in self.actions.items() if v != "none"}
            if not active_targets:
                self.query_one("#preview_log").write("[red]❌ План пуст! Выберите действия перед выполнением.[/red]")
                return
            self.exit(self.actions)

