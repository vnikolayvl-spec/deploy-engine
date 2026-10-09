#!/usr/bin/env python3
"""
Кастомный виджет интерактивного иерархического дерева пакетов.
"""
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from lib.modules.state_manager import load_state

class InfrastructureTree(Tree):
    def __init__(self, engine, app_instance, **kwargs):
        # Передаем строку корня дерева в конструктор родителя
        super().__init__("Проекты infrastructure", **kwargs)
        self.engine = engine
        self.app_ref = app_instance  # Ссылка на главное приложение для обновления логов
        self.system_state = load_state()

    def on_mount(self) -> None:
        """Построение иерархии пакетов при монтировании виджета"""
        self.root.expand()

        # 1. Собираем все включенные элементы со всех пакетов.
        # Если элемент содержит двоеточие (пространство имен), берем его чистую финальную часть.
        all_includes = set()
        for p_info in self.engine.packages.values():
            for item in p_info.get("include", []):
                clean_item = item.split(":")[-1]
                all_includes.add(clean_item)

        # 2. Добавляем только независимые корневые пакеты (которых нет в чужих списках include)
        for p_name in sorted(self.engine.packages.keys()):
            if p_name not in all_includes:
                self._build_tree_recursive(self.root, p_name)

        # 3. Добавляем файлы, которые вообще не входят в пакеты (сироты)
        for u_name in sorted(self.engine.units.keys()):
            clean_unit = u_name.split(":")[-1]
            if clean_unit not in all_includes and u_name not in all_includes:
                desc = self.engine.units[u_name].get("desc", "Без описания")
                label = f"[ ] 📄 Одиночный файл: {clean_unit} ({desc})"
                self.root.add(label, data={"key": u_name, "is_package": False})

    def _build_tree_recursive(self, parent_node: TreeNode, item_name: str):
        """Рекурсивно строит дерево с подсветкой установленных пакетов"""
        installed_packages = self.system_state.get("installed_packages", {})
        
        # Получаем чистое имя без префикса папки для проверки в словарях пакетов
        clean_name = item_name.split(":")[-1]

        if clean_name in self.engine.packages:
            p_info = self.engine.packages[clean_name]

            if clean_name in installed_packages:
                label = f"[ ] [bold green]🎁 Пакет: {clean_name} [УСТАНОВЛЕН][/bold green] ({p_info.get('desc', '')})"
            else:
                label = f"[ ] 🎁 Пакет: {clean_name} ({p_info.get('desc', '')})"

            node = parent_node.add(label, data={"key": clean_name, "is_package": True})
            
            # Рекурсивно уходим вглубь по элементам внутри include
            for child in p_info.get("include", []):
                self._build_tree_recursive(node, child)
                
        elif item_name in self.engine.units:
            u_info = self.engine.units[item_name]
            icon = "🔗 Симлинк:" if u_info.get("type") == "symlink" else "📄 Файл:"
            label = f"[ ] {icon} {clean_name} ({u_info.get('desc', '')})"
            parent_node.add(label, data={"key": item_name, "is_package": False})

    def handle_left_right_keys(self, key_name: str) -> None:
        """Нативная навигация стрелками Вправо/Влево по уровням иерархии"""
        node = self.cursor_node
        if not node or not node.data: return

        if key_name == "right":
            if node.data.get("is_package"):
                if not node.is_expanded:
                    node.expand()
                elif node.children:
                    self.select_node(node.children[0])
        elif key_name == "left":
            if node.data.get("is_package") and node.is_expanded:
                node.collapse()
            else:
                if node.parent and node.parent != self.root:
                    self.select_node(node.parent)

    def handle_space_press(self) -> None:
        """Переключает статус действия для текущего пакета по кругу через Пробел"""
        node = self.cursor_node
        if not node or not node.data or not node.data.get("is_package"):
            return

        key = node.data["key"]
        current_action = self.app_ref.actions.get(key, "none")
        installed_packages = self.system_state.get("installed_packages", {})

        if key in installed_packages:
            if current_action == "none": next_action = "reinstall"
            elif current_action == "reinstall": next_action = "uninstall"
            else: next_action = "none"
        else:
            if current_action == "none": next_action = "install"
            else: next_action = "none"

        self._set_action_recursive(node, next_action)
        # Дергаем метод обновления сводного плана в главном приложении
        self.app_ref.render_live_preview()

    def _set_action_recursive(self, node: TreeNode, action_type: str):
        """Рекурсивно меняет текстовые маркеры и наполняет общую карту действий"""
        if not node.data: return
        key = node.data["key"]

        installed_packages = self.system_state.get("installed_packages", {})
        if action_type in ["uninstall", "reinstall"] and key not in installed_packages and node.data.get("is_package"):
            return

        self.app_ref.actions[key] = action_type

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

    def on_key(self, event) -> None:
        """Перехват клавиш на уровне самого виджета дерева"""
        if event.key == "space":
            self.handle_space_press()
            event.prevent_default()
        elif event.key in ["right", "left"]:
            self.handle_left_right_keys(event.key)
            event.prevent_default()

