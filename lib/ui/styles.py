#!/usr/bin/env python3
"""
Глобальные стили CSS для TUI-интерфейса деплоера.
"""

APP_CSS = """
Screen {
    align: center middle;
}
#main_container {
    width: 85%;
    height: 85%;
    border: solid $primary;
    background: $panel;
    padding: 1;
}
Label {
    margin: 1 0;
    text-style: bold;
}
InfrastructureTree {
    height: 45%;
    border: round $accent;
    margin-bottom: 1;
    background: $surface;
}
PlanPreviewLog {
    height: 30%;
    border: solid $secondary;
    background: $surface;
    margin-bottom: 1;
}
Horizontal {
    height: auto;
    align: center middle;
}
Button {
    margin: 0 2;
}
"""

