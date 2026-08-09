#!/usr/bin/env python3
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, SelectionList, Label, Button, RichLog
from textual.widgets.selection_list import Selection
from textual.containers import Vertical, Horizontal

class DeployApp(App):
    TITLE = "Independent Infrastructure Deployer"
    CSS = """
    Screen { align: center middle; }
    #main_container { width: 85%; height: 85%; border: solid $primary; background: $panel; padding: 1; }
    Label { margin: 1 0; text-style: bold; }
    SelectionList { height: 45%; border: round $accent; margin-bottom: 1; }
    RichLog { height: 30%; border: solid $secondary; background: $surface; margin-bottom: 1; }
    Horizontal { height: auto; align: center middle; }
    Button { margin: 0 2; }
    """

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.selected_targets = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main_container"):
            yield Label("[green]Манифест успешно загружен со всеми инклудами![/green] Выберите компоненты:")
            selections = []
            for p_name, p_info in self.engine.packages.items():
                selections.append(Selection(f"🎁 Пакет: {p_name} ({p_info.get('desc')})", p_name))
            for u_name, u_info in self.engine.units.items():
                selections.append(Selection(f"📄 Файл: {u_name} ({u_info.get('desc')})", u_name))
            yield SelectionList(*selections, id="select_list")
            yield Label("Карта путей установки (Рендеринг изменений на лету):")
            yield RichLog(id="preview_log", highlight=True, markup=True)
            with Horizontal():
                yield Button("Установить", variant="success", id="btn_install")
                yield Button("Выход", variant="error", id="btn_exit")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#preview_log").write("[yellow]Выберите компоненты выше, чтобы увидеть карту путей...[/yellow]")

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        self.selected_targets = event.selection_list.selected
        log = self.query_one("#preview_log")
        log.clear()
        if not self.selected_targets:
            log.write("[yellow]Выберите компоненты...[/yellow]")
            return

        self.engine.files_to_deploy.clear()
        for t in self.selected_targets:
            self.engine.resolve_dependencies(t)

        log.write(f"[bold green]Будет обработано файлов: {len(self.engine.files_to_deploy)}[/bold green]\n" + "-"*50)
        for fname in sorted(self.engine.files_to_deploy):
            src, dest, mode, _ = self.engine.get_paths_and_modes(fname)
            desc = self.engine.units.get(fname, {}).get("desc", "")
            if src == "NOT_FOUND":
                log.write(f"[red]❌ ОШИБКА: Файл {fname} отсутствует на диске![/red]")
            else:
                log.write(f"🔹 [bold]{fname}[/bold] ({desc})\n   [cyan]Куда:[/cyan] {dest} | [cyan]Права:[/cyan] {oct(mode)[2:]}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_exit": self.exit()
        elif event.button.id == "btn_install":
            if not self.selected_targets: return
            self.exit(self.selected_targets)
