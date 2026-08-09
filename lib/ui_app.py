#!/usr/bin/env python3
"""
Графический интерфейс Amnezia Deployer на базе Иерархического Textual Tree.
Рекурсивно строит вложенную структуру пакетов (пакеты внутри пакетов) и файлов,
отображая честные зависимости и связи из manifest.json.
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Label, Button, RichLog
from textual.containers import Vertical, Horizontal
from textual.widgets.tree import TreeNode

class DeployApp(App):
    TITLE = "Independent Hierarchical Deployer"
    
    CSS = """
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
    Tree {
        height: 45%;
        border: round $accent;
        margin-bottom: 1;
        background: $surface;
    }
    RichLog {
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

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        # Храним статусы выбора: ключ (пакет или файл) -> bool (выбран/нет)
        self.selected_states = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main_container"):
            yield Label("Иерархическое дерево пакетов (Пробел — выбрать группу/файл, Enter — развернуть ветку):")
            
            yield Tree("Проекты инфраструктуры", id="packages_tree")
            
            yield Label("Карта путей установки выбранных элементов (Рендеринг на лету):")
            yield RichLog(id="preview_log", highlight=True, markup=True)
            
            with Horizontal():
                yield Button("Установить", variant="success", id="btn_install")
                yield Button("Выход", variant="error", id="btn_exit")
        yield Footer()

    def on_mount(self) -> None:
        """Точка старта построения дерева"""
        tree = self.query_one("#packages_tree")
        tree.root.expand()
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Передаем фокус дереву, чтобы сразу работали стрелки!
        tree.focus()
        
        # Чтобы дерево не дублировало пакеты, которые уже вложены в другие,
        # найдем "корневые" пакеты — те, которые никто не включает в себя.
        all_includes = set()
        for p_info in self.engine.packages.values():
            for item in p_info.get("include", []):
                all_includes.add(item)
                
        # Инициализируем статусы для всех компонентов в False
        for p_name in self.engine.packages: self.selected_states[p_name] = False
        for u_name in self.engine.units: self.selected_states[u_name] = False

        # 1. Строим дерево рекурсивно, начиная только с независимых корневых пакетов
        for p_name in sorted(self.engine.packages.keys()):
            if p_name not in all_includes:
                self._build_tree_recursive(tree.root, p_name)

        # 2. Добавляем файлы, которые вообще не привязаны ни к одному пакету (сироты)
        for u_name in sorted(self.engine.units.keys()):
            if u_name not in all_includes:
                desc = self.engine.units[u_name].get("desc", "Без описания")
                label = f"[ ] 📄 Одиночный файл: {u_name} ({desc})"
                tree.root.add(label, data={"key": u_name, "is_package": False})

        self.query_one("#preview_log").write("[yellow]Используйте ПРОБЕЛ для выбора пакетов в дереве...[/yellow]")


    def _build_tree_recursive(self, parent_node: TreeNode, item_name: str):
        """Рекурсивная функция сборки дерева для визуализации 'матрешек'"""
        if item_name in self.engine.packages:
            # Это пакет. Создаем для него красивую ветку-папку
            p_info = self.engine.packages[item_name]
            label = f"[ ] 🎁 Пакет: {item_name} ({p_info.get('desc', '')})"
            node = parent_node.add(label, data={"key": item_name, "is_package": True})
            
            # Спускаемся глубже по его зависимостям
            for child in p_info.get("include", []):
                self._build_tree_recursive(node, child)
                
        elif item_name in self.engine.units:
            # Это конечный файл. Создаем лист дерева
            u_info = self.engine.units[item_name]
            label = f"[ ] 📄 Файл: {item_name} ({u_info.get('desc', '')})"
            parent_node.add(label, data={"key": item_name, "is_package": False})

    # def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
    #     """Разворачивание/сворачивание веток по клавише Enter"""
    #     node = event.node
    #     if node.data and node.data.get("is_package"):
    #         node.toggle()

    def handle_space_press(self) -> None:
        """Переключатель чекбоксов по пробелу с рекурсивным выделением детей"""
        tree = self.query_one("#packages_tree")
        node = tree.cursor_node
        
        if not node or not node.data:
            return
            
        key = node.data["key"]
        new_state = not self.selected_states.get(key, False)
        
        # Запускаем рекурсивное обновление состояния этого узла и всех его визуальных детей
        self._toggle_node_and_children(node, new_state)

        # Перерисовываем RichLog карту путей
        self.render_live_preview()

    def _toggle_node_and_children(self, node: TreeNode, state: bool):
        """Рекурсивно проставляет [X] или [ ] текущему узлу и всему, что внутри него"""
        if not node.data:
            return
            
        key = node.data["key"]
        self.selected_states[key] = state
        
        # Обновляем текст на экране
        current_label = str(node.label)
        if current_label.startswith("[ ]") or current_label.startswith("[X]"):
            node.label = f"{'[X]' if state else '[ ]'}{current_label[3:]}"
            
        # Идем вглубь по подветкам дерева
        for child in node.children:
            self._toggle_node_and_children(child, state)

    def render_live_preview(self) -> None:
        """Рендеринг путей для RichLog лога"""
        log = self.query_one("#preview_log")
        log.clear()
        
        active_targets = [k for k, v in self.selected_states.items() if v]
        if not active_targets:
            log.write("[yellow]Используйте ПРОБЕЛ для выбора пакетов в дереве...[/yellow]")
            return

        self.engine.files_to_deploy.clear()
        for target in active_targets:
            self.engine.resolve_dependencies(target)

        log.write(f"[bold green]Будет обработано уникальных файлов: {len(self.engine.files_to_deploy)}[/bold green]\n" + "-"*50)
        for fname in sorted(self.engine.files_to_deploy):
            src, dest, mode, _ = self.engine.get_paths_and_modes(fname)
            desc = self.engine.units.get(fname, {}).get("desc", "")
            if src == "NOT_FOUND":
                log.write(f"[red]❌ ОШИБКА: Файл {fname} отсутствует на диске пакетов![/red]")
            else:
                log.write(f"🔹 [bold]{fname}[/bold] ({desc})\n   [cyan]Куда:[/cyan] {dest} | [cyan]Права:[/cyan] {oct(mode)[2:]}")

    def handle_left_right_keys(self, key_name: str) -> None:
        """Обработчик стрелок Вправо/Влево для управления раскрытием дерева"""
        tree = self.query_one("#packages_tree")
        node = tree.cursor_node
        
        if not node or not node.data:
            return
            
        if key_name == "right":
            if node.data.get("is_package"):
                if not node.is_expanded:
                    node.expand()
                elif node.children:
                    # Используем безопасный метод выбора узла
                    tree.select_node(node.children[0])
                    
        elif key_name == "left":
            if node.data.get("is_package") and node.is_expanded:
                node.collapse()
            else:
                if node.parent and node.parent != tree.root:
                    # Используем безопасный метод выбора узла
                    tree.select_node(node.parent)

    def on_key(self, event) -> None:
        """Единый диспетчер клавиатурных событий приложения"""
        if event.key == "space":
            self.handle_space_press()
            event.prevent_default()
        elif event.key in ["right", "left"]:
            self.handle_left_right_keys(event.key)
            event.prevent_default()


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_exit":
            self.exit()
        elif event.button.id == "btn_install":
            active_targets = [k for k, v in self.selected_states.items() if v]
            if not active_targets:
                self.query_one("#preview_log").write("[red]❌ Ничего не выбрано для установки![/red]")
                return
            self.exit(active_targets)
