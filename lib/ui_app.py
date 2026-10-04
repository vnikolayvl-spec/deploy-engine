#!/usr/bin/env python3
"""
Иерархический интерфейс Deployer с трехфлажковой циклической системой действий.
Управление через Пробел:
  - Для новых пакетов:    [ ] Ничего -> [+] Установить -> [ ] Ничего
  - Для установленных:    [ ] Ничего -> [↻] Переустановить -> [-] Удалить -> [ ] Ничего
"""
import os
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, Label, Button, RichLog
from textual.containers import Vertical, Horizontal
from textual.widgets.tree import TreeNode

from lib.modules.state_manager import load_state

class DeployApp(App):
    TITLE = "Independent Multi-Action Deployer"
    
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
        # Карта запланированных действий: имя_компонента -> action ("install", "reinstall", "uninstall", "none")
        self.actions = {}
        self.system_state = load_state()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main_container"):
            yield Label("Управление пакетами: Пробел — Циклическое переключение действий, Стрелки Право/Лево — Раскрыть/Свернуть")
            
            yield Tree("Проекты infrastructure", id="packages_tree")
            
            yield Label("Сводный план выполнения операций (Рендеринг на лету):")
            yield RichLog(id="preview_log", highlight=True, markup=True)
            
            with Horizontal():
                yield Button("Выполнить план", variant="success", id="btn_run")
                yield Button("Выход", variant="error", id="btn_exit")
        yield Footer()

    def on_mount(self) -> None:
        """Точка старта построения дерева веток"""
        tree = self.query_one("#packages_tree")
        tree.root.expand()
        tree.focus()
        
        all_includes = set()
        for p_info in self.engine.packages.values():
            for item in p_info.get("include", []):
                all_includes.add(item)
                
        # Инициализируем действия по умолчанию для всех элементов
        for p_name in self.engine.packages: self.actions[p_name] = "none"
        for u_name in self.engine.units: self.actions[u_name] = "none"

        # 1. Рекурсивно строим дерево с независимых корневых пакетов
        for p_name in sorted(self.engine.packages.keys()):
            if p_name not in all_includes:
                self._build_tree_recursive(tree.root, p_name)

        # 2. Добавляем файлы, которые вообще не входят в пакеты (сироты)
        for u_name in sorted(self.engine.units.keys()):
            if u_name not in all_includes:
                desc = self.engine.units[u_name].get("desc", "Без описания")
                label = f"[ ] 📄 Одиночный файл: {u_name} ({desc})"
                tree.root.add(label, data={"key": u_name, "is_package": False})

        self.render_live_preview()

    def _build_tree_recursive(self, parent_node: TreeNode, item_name: str):
        """Рекурсивно строит дерево с подсветкой установленных пакетов"""
        installed_packages = self.system_state.get("installed_packages", {})

        if item_name in self.engine.packages:
            p_info = self.engine.packages[item_name]
            
            # Если пакет найден в state.json, красим его зеленым
            if item_name in installed_packages:
                label = f"[ ] [bold green]🎁 Пакет: {item_name} [УСТАНОВЛЕН][/bold green] ({p_info.get('desc', '')})"
            else:
                label = f"[ ] 🎁 Пакет: {item_name} ({p_info.get('desc', '')})"
                
            node = parent_node.add(label, data={"key": item_name, "is_package": True})
            for child in p_info.get("include", []):
                self._build_tree_recursive(node, child)
        elif item_name in self.engine.units:
            u_info = self.engine.units[item_name]
            icon = "🔗 Симлинк:" if u_info.get("type") == "symlink" else "📄 Файл:"
            label = f"[ ] {icon} {item_name} ({u_info.get('desc', '')})"
            parent_node.add(label, data={"key": item_name, "is_package": False})

    def handle_left_right_keys(self, key_name: str) -> None:
        """Нативная навигация стрелками Вправо/Влево по уровням иерархии"""
        tree = self.query_one("#packages_tree")
        node = tree.cursor_node
        if not node or not node.data: return
            
        if key_name == "right":
            if node.data.get("is_package"):
                if not node.is_expanded:
                    node.expand()
                elif node.children:
                    tree.select_node(node.children)
        elif key_name == "left":
            if node.data.get("is_package") and node.is_expanded:
                node.collapse()
            else:
                if node.parent and node.parent != tree.root:
                    tree.select_node(node.parent)

    def handle_space_press(self) -> None:
        """Переключает статус действия для текущего пакета по кругу через Пробел"""
        tree = self.query_one("#packages_tree")
        node = tree.cursor_node
        if not node or not node.data or not node.data.get("is_package"):
            return # Ограничиваем циклы только пакетами для предсказуемости
            
        key = node.data["key"]
        current_action = self.actions.get(key, "none")
        installed_packages = self.system_state.get("installed_packages", {})

        # ВЫЧИСЛЯЕМ СЛЕДУЮЩЕЕ СОСТОЯНИЕ В ЦИКЛЕ
        if key in installed_packages:
            # Для установленных: none -> reinstall -> uninstall -> none
            if current_action == "none": next_action = "reinstall"
            elif current_action == "reinstall": next_action = "uninstall"
            else: next_action = "none"
        else:
            # Для новых: none -> install -> none
            if current_action == "none": next_action = "install"
            else: next_action = "none"

        # Запускаем каскадный спуск вниз по дочерним веткам
        self._set_action_recursive(node, next_action)
        self.render_live_preview()

    def _set_action_recursive(self, node: TreeNode, action_type: str):
        """Рекурсивно меняет текстовые маркеры и наполняет карту действий"""
        if not node.data: return
        key = node.data["key"]
        
        installed_packages = self.system_state.get("installed_packages", {})
        # Защита: нельзя снести или переустановить пакет, которого нет в state.json
        if action_type in ["uninstall", "reinstall"] and key not in installed_packages and node.data.get("is_package"):
            return

        self.actions[key] = action_type
        
        # Подбираем визуальный маркер
        marker = "[ ]"
        if action_type == "install": marker = "[+]"
        elif action_type == "reinstall": marker = "[↻]"
        elif action_type == "uninstall": marker = "[-]"

        current_label = str(node.label)
        for old_m in ["[ ]", "[+]", "[↻]", "[-]"]:
            if current_label.startswith(old_m):
                node.label = f"{marker}{current_label[3:]}"
                break
            
        for child in node.children:
            self._set_action_recursive(child, action_type)

    def render_live_preview(self) -> None:
        """Группирует действия по трем секциям в нижнем окне логов на лету"""
        log = self.query_one("#preview_log")
        log.clear()
        
        plans = {"install": set(), "reinstall": set(), "uninstall": set()}
        for k, v in self.actions.items():
            if v in plans: plans[v].add(k)
            
        if not plans["install"] and not plans["reinstall"] and not plans["uninstall"]:
            log.write("[yellow]Используйте ПРОБЕЛ на пакетах для планирования операций...[/yellow]")
            return

        import deploy_config as config
        
        # Секция 1: Удаление
        if plans["uninstall"]:
            log.write("[bold red]🚨 ПЛАН УДАЛЕНИЯ ПАКЕТОВ (ЭТАП 1):[/bold red]")
            for pkg in sorted(plans["uninstall"]):
                log.write(f"  [-] Пакет [bold]{pkg}[/bold] будет полностью стерт из системы")

        # Секция 2 и 3: Переустановка и Установка
        for mode in ["reinstall", "install"]:
            if not plans[mode]: continue
            title = "🔄 ПЛАН ПОЛНОЙ ПЕРЕУСТАНОВКИ (ЭТАП 2):" if mode == "reinstall" else "🎁 ПЛАН УСТАНОВКИ НОВЫХ ПАКЕТОВ (ЭТАП 3):"
            color = "yellow" if mode == "reinstall" else "green"
            
            log.write(f"\n[bold {color}]{title}[/bold {color}]")
            
            self.engine.files_to_deploy.clear()
            for pkg in plans[mode]:
                self.engine.resolve_dependencies(pkg)
                
            # ИСПРАВЛЕНО: Теперь ссылаемся строго на self.engine.files_to_deploy
            for fname in sorted(self.engine.files_to_deploy):
                file_info = self.engine.units.get(fname, {})
                base_dir = os.path.abspath(file_info.get("base_dir", "."))
                root_dir = os.path.abspath(file_info.get("root_dir", "."))
                
                src, dest, mode_mask, f_type = self.engine.get_paths_and_modes(fname)
                desc = file_info.get("desc", "")
                
                context_vars = {
                    "{{ROOT_DIR}}": root_dir,
                    "{{BASE_DIR}}": base_dir,
                    "{{SYS_BIN}}": config.SYS_BIN,
                    "{{SYS_SYSTEMD}}": config.SYS_SYSTEMD
                }
                for marker, real_value in context_vars.items():
                    if src != "NOT_FOUND": src = src.replace(marker, real_value)
                    dest = dest.replace(marker, real_value)
                    
                if f_type == "symlink":
                    log.write(f"   🔗 [Симлинк] {fname} ({desc}) -> {dest}")
                else:
                    log.write(f"   🔹 [Файл]    {fname} ({desc}) -> {dest}")

    def on_key(self, event) -> None:
        if event.key == "space":
            self.handle_space_press()
            event.prevent_default()
        elif event.key in ["right", "left"]:
            self.handle_left_right_keys(event.key)
            event.prevent_default()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_exit":
            self.exit()
        elif event.button.id == "btn_run":
            active_targets = {k: v for k, v in self.actions.items() if v != "none"}
            if not active_targets:
                self.query_one("#preview_log").write("[red]❌ План пуст! Выберите действия перед выполнением.[/red]")
                return
            self.exit(self.actions)

