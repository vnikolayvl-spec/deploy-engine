#!/usr/bin/env python3
"""
Кастомный виджет интерактивного иерархического дерева пакетов.
Отображает структуру каталогов, описания из манифестов, вложенные пакеты и их юниты.
"""
import os
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from lib.state.state_repository import StateRepository


class InfrastructureTree(Tree):
    """Иерархическое дерево каталогов, пакетов и юнитов."""

    def __init__(self, engine, app_instance, **kwargs):
        super().__init__("Инфраструктура пакетов", **kwargs)
        self.engine = engine
        self.app_ref = app_instance
        state_data = StateRepository().get_state()
        installed = state_data.get("installed", {}) or state_data.get("installed_packages", {})
        self.system_state = {"installed_packages": installed, "installed": installed}

    def on_mount(self) -> None:
        """Построение иерархии дерева при монтировании виджета."""
        self.root.expand()

        # 1. Вычисляем базовый корневой каталог
        all_dirs = [p.get("base_dir") for p in self.engine.packages.values() if p.get("base_dir")]
        common_root = os.path.commonpath(all_dirs) if all_dirs else os.getcwd()

        root_folder_name = os.path.basename(common_root)
        root_desc = ""
        if hasattr(self.engine, "registry"):
            root_desc = self.engine.registry.get_folder_desc(root_folder_name)
        if root_desc:
            self.root.label = f"[bold cyan]📁 {root_folder_name}/[/bold cyan] [dim]({root_desc})[/dim]"
        elif root_folder_name:
            self.root.label = f"[bold cyan]📁 {root_folder_name}/[/bold cyan]"

        # 2. Строим иерархическую структуру дерева каталогов
        tree_root = {"folders": {}, "packages": []}
        for full_ns, p_info in sorted(self.engine.packages.items()):
            bd = p_info.get("base_dir", "")
            rel_dir = os.path.relpath(bd, common_root) if bd else "."
            parts = [] if rel_dir == "." else [p for p in rel_dir.split(os.sep) if p and p != "."]

            curr = tree_root
            for part in parts:
                curr = curr["folders"].setdefault(part, {"folders": {}, "packages": []})
            curr["packages"].append((full_ns, p_info))

        # 3. Рекурсивно монтируем папки и пакеты
        self._mount_directory_branch(self.root, tree_root, "")

    def _mount_directory_branch(self, parent_node: TreeNode, branch_dict: dict, current_path: str) -> None:
        """Монтирует ветку папок и пакетов в дерево."""
        folders = branch_dict.get("folders", {})
        for folder_name in sorted(folders.keys()):
            sub_path = f"{current_path}/{folder_name}" if current_path else folder_name
            folder_desc = ""
            if hasattr(self.engine, "registry"):
                folder_desc = self.engine.registry.get_folder_desc(sub_path) or self.engine.registry.get_folder_desc(folder_name)

            desc_str = f" [dim]({folder_desc})[/dim]" if folder_desc else ""
            folder_node = parent_node.add(
                f"[bold cyan]📁 {folder_name}/[/bold cyan]{desc_str}",
                data={"key": sub_path, "is_folder": True, "is_package": False},
            )
            folder_node.expand()
            self._mount_directory_branch(folder_node, folders[folder_name], sub_path)

        # Монтируем пакеты в текущей директории
        packages = branch_dict.get("packages", [])
        installed_map = self.system_state.get("installed", {})

        for full_ns, p_info in packages:
            pkg_name = p_info.get("name", full_ns)
            is_installed = (pkg_name in installed_map) or (full_ns in installed_map)
            desc = p_info.get("description") or p_info.get("desc") or ""
            desc_str = f" ({desc})" if desc else ""

            if is_installed:
                label = f"[ ] [bold green]🎁 Пакет: {pkg_name} [УСТАНОВЛЕН][/bold green]{desc_str}"
            else:
                label = f"[ ] 🎁 Пакет: {pkg_name}{desc_str}"

            pkg_node = parent_node.add(
                label,
                data={
                    "key": full_ns,
                    "pkg_name": pkg_name,
                    "is_package": True,
                    "is_folder": False,
                },
            )

            # Добавляем все юниты данного пакета внутрь узла пакета
            self._mount_package_units(pkg_node, pkg_name, p_info)

    def _mount_package_units(self, pkg_node: TreeNode, pkg_name: str, p_info: dict) -> None:
        """Добавляет юниты пакета как дочерние элементы под узлом пакета."""
        units = p_info.get("units", {})
        if not units:
            return

        for u_name, u_spec in sorted(units.items()):
            u_spec = u_spec or {}
            u_type = u_spec.get("type")
            if not u_type:
                if u_name.endswith(".sh") or u_name.endswith(".py"):
                    u_type = "script"
                elif u_name.endswith(".service"):
                    u_type = "service"
                elif u_name.endswith(".timer"):
                    u_type = "timer"
                elif u_name.endswith(".env") or u_name == "deploy.env":
                    u_type = "env"
                elif u_spec.get("symlink"):
                    u_type = "symlink"
                else:
                    u_type = "file"

            if u_type == "env":
                icon = "🔐 ENV:"
            elif u_type in ["unit", "service"]:
                icon = "⚙️ Служба:"
            elif u_type == "timer":
                icon = "⏱️ Таймер:"
            elif u_type == "script":
                icon = "📜 Скрипт:"
            elif u_type == "data":
                icon = "💾 Данные:"
            elif u_type == "symlink":
                icon = "🔗 Симлинк:"
            else:
                icon = "📄 Файл:"

            u_desc = u_spec.get("desc", "")
            u_desc_str = f" ({u_desc})" if u_desc else ""
            unit_label = f"[ ] {icon} {u_name}{u_desc_str}"

            pkg_node.add(
                unit_label,
                data={
                    "key": f"{pkg_name}:{u_name}",
                    "is_package": False,
                    "is_folder": False,
                    "is_unit": True,
                    "pkg_name": pkg_name,
                    "unit_name": u_name,
                },
            )

    def handle_left_right_keys(self, key_name: str) -> None:
        """Навигация стрелками Вправо/Влево по уровням иерархии."""
        node = self.cursor_node
        if not node or not node.data:
            return

        is_container = node.data.get("is_package") or node.data.get("is_folder")
        if key_name == "right":
            if is_container:
                if not node.is_expanded:
                    node.expand()
                elif node.children:
                    self.select_node(node.children[0])
        elif key_name == "left":
            if is_container and node.is_expanded:
                node.collapse()
            else:
                if node.parent and node.parent != self.root:
                    self.select_node(node.parent)

    def handle_space_press(self) -> None:
        """Переключает статус действия для текущего узла через Пробел."""
        node = self.cursor_node
        if not node or not node.data:
            return

        # 1. Если нажат конкретный пакет
        if node.data.get("is_package"):
            pkg_key = node.data["key"]
            pkg_name = node.data.get("pkg_name", pkg_key)
            installed_map = self.system_state.get("installed", {})

            current_action = self.app_ref.actions.get(pkg_name) or self.app_ref.actions.get(pkg_key, "none")

            if pkg_name in installed_map or pkg_key in installed_map:
                if current_action == "none":
                    next_action = "reinstall"
                elif current_action == "reinstall":
                    next_action = "uninstall"
                else:
                    next_action = "none"
            else:
                if current_action == "none":
                    next_action = "install"
                else:
                    next_action = "none"

            self._apply_action_to_package(node, next_action)
            self.app_ref.render_live_preview()

        # 2. Если нажата папка (директория)
        elif node.data.get("is_folder"):
            current_action = self.app_ref.actions.get(node.data["key"], "none")
            next_action = "install" if current_action == "none" else "none"
            self.app_ref.actions[node.data["key"]] = next_action
            self._apply_action_to_folder(node, next_action)
            self.app_ref.render_live_preview()

    def _apply_action_to_package(self, pkg_node: TreeNode, action: str) -> None:
        """Применяет действие только к пакету, визуально обновляя дочерние юниты."""
        pkg_key = pkg_node.data.get("key")
        pkg_name = pkg_node.data.get("pkg_name", pkg_key)

        # Сохраняем действие исключительно для имени пакета
        if action == "none":
            self.app_ref.actions.pop(pkg_name, None)
            self.app_ref.actions.pop(pkg_key, None)
        else:
            self.app_ref.actions[pkg_name] = action
            if pkg_key != pkg_name:
                self.app_ref.actions[pkg_key] = action

        marker = self._get_marker(action)
        self._update_node_marker(pkg_node, marker)

        # Визуально обновляем маркеры всех дочерних юнитов
        for child in pkg_node.children:
            self._update_node_marker(child, marker)

    def _apply_action_to_folder(self, folder_node: TreeNode, action: str) -> None:
        """Рекурсивно применяет действие ко всем пакетам внутри папки."""
        marker = self._get_marker(action)
        self._update_node_marker(folder_node, marker)

        for child in folder_node.children:
            if child.data.get("is_package"):
                self._apply_action_to_package(child, action)
            elif child.data.get("is_folder"):
                self._apply_action_to_folder(child, action)

    def _get_marker(self, action: str) -> str:
        """Возвращает маркер состояния."""
        if action == "install":
            return "[+]"
        elif action == "reinstall":
            return "[↻]"
        elif action == "uninstall":
            return "[-]"
        return "[ ]"

    def _update_node_marker(self, node: TreeNode, marker: str) -> None:
        """Обновляет префикс маркера у узла."""
        current_label = str(node.label)
        for old_m in ["[ ]", "[+]", "[↻]", "[-]"]:
            if current_label.startswith(old_m):
                node.label = f"{marker}{current_label[3:]}"
                return
        node.label = f"{marker} {current_label}"

    def on_key(self, event) -> None:
        """Перехват клавиш на уровне виджета дерева."""
        if event.key == "space":
            self.handle_space_press()
            event.prevent_default()
        elif event.key in ["right", "left"]:
            self.handle_left_right_keys(event.key)
            event.prevent_default()
