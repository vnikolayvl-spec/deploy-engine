#!/usr/bin/env python3
"""
Кастомный виджет интерактивного иерархического дерева пакетов.
Строит дерево строго по иерархии папок с manifest.json, отображает описания папок (desc),
вложенные пакеты и юниты внутри пакетов.
"""
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
        """Построение иерархии дерева по реальной структуре папок и манифестов."""
        self.root.expand()

        tree_structure = {
            "folders": {},
            "packages": {},
            "desc": "",
            "full_path": "",
        }

        # 1. Регистрируем все папки из реестра (включая пустые и содержащие только desc)
        folders_map = getattr(self.engine, "folders", {})
        for folder_path, f_info in sorted(folders_map.items()):
            parts = [p for p in folder_path.split("/") if p and p != "."]
            curr = tree_structure
            built_parts = []
            for part in parts:
                built_parts.append(part)
                curr = curr["folders"].setdefault(
                    part,
                    {
                        "folders": {},
                        "packages": {},
                        "desc": "",
                        "full_path": "/".join(built_parts),
                    },
                )
            if f_info.get("desc"):
                curr["desc"] = f_info["desc"]

        # 2. Размещаем пакеты в соответствующие папки согласно их folder_path
        for reg_key, p_info in sorted(self.engine.packages.items()):
            if p_info.get("is_alias"):
                continue

            folder_path = p_info.get("folder_path", "")
            parts = [p for p in folder_path.split("/") if p and p != "."]
            curr = tree_structure
            built_parts = []
            for part in parts:
                built_parts.append(part)
                curr = curr["folders"].setdefault(
                    part,
                    {
                        "folders": {},
                        "packages": {},
                        "desc": "",
                        "full_path": "/".join(built_parts),
                    },
                )
            pkg_name = p_info.get("name", reg_key.split("/")[-1])
            curr["packages"][pkg_name] = (reg_key, p_info)

        # 3. Рекурсивно монтируем узлы папок, пакетов и их юнитов
        self._mount_directory_branch(self.root, tree_structure)

    def _mount_directory_branch(self, parent_node: TreeNode, branch_dict: dict) -> None:
        """Монтирует ветку папок и пакетов в дерево."""
        folders = branch_dict.get("folders", {})
        for folder_name in sorted(folders.keys()):
            f_node_data = folders[folder_name]
            f_desc = f_node_data.get("desc", "")
            desc_suffix = f" ({f_desc})" if f_desc else ""
            full_path = f_node_data.get("full_path") or folder_name

            folder_node = parent_node.add(
                f"[ ] [bold cyan]📁 {folder_name}/[/bold cyan]{desc_suffix}",
                data={
                    "key": f"folder:{full_path}",
                    "folder_path": full_path,
                    "is_folder": True,
                    "is_package": False,
                    "folder_action": "none",
                },
            )
            folder_node.expand()
            self._mount_directory_branch(folder_node, f_node_data)

        packages = branch_dict.get("packages", {})
        installed_map = self.system_state.get("installed", {})

        for pkg_name, (reg_key, p_info) in sorted(packages.items()):
            is_installed = (pkg_name in installed_map) or (reg_key in installed_map)
            desc = p_info.get("description") or p_info.get("desc") or ""
            desc_str = f" ({desc})" if desc else ""

            if is_installed:
                label = f"[ ] [bold green]🎁 Пакет: {pkg_name} [УСТАНОВЛЕН][/bold green]{desc_str}"
            else:
                label = f"[ ] 🎁 Пакет: {pkg_name}{desc_str}"

            pkg_node = parent_node.add(
                label,
                data={
                    "key": reg_key,
                    "pkg_name": pkg_name,
                    "is_package": True,
                    "is_folder": False,
                },
            )

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
        """Переключает статус действия для текущего пакета или папки через Пробел."""
        node = self.cursor_node
        if not node or not node.data:
            return

        # Если выбор сделан на юните внутри пакета — переключаем родительский пакет
        if not node.data.get("is_package") and not node.data.get("is_folder"):
            if node.parent and node.parent.data and node.parent.data.get("is_package"):
                node = node.parent
            else:
                return

        if node.data.get("is_package"):
            pkg_key = node.data["key"]
            current_action = self.app_ref.actions.get(pkg_key, "none")
            installed_map = self.system_state.get("installed", {})
            pkg_name = node.data.get("pkg_name", pkg_key)

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

            self._set_action_recursive(node, next_action)
            self.app_ref.render_live_preview()

        elif node.data.get("is_folder"):
            current_action = node.data.get("folder_action", "none")
            next_action = "install" if current_action == "none" else "none"
            node.data["folder_action"] = next_action
            self._set_action_recursive(node, next_action)
            self.app_ref.render_live_preview()

    def _set_action_recursive(self, node: TreeNode, action_type: str) -> None:
        """
        Рекурсивно меняет текстовые маркеры узлов и записывает в self.app_ref.actions
        ТОЛЬКО реальные пакеты (is_package=True), исключая папки и дочерние юниты.
        """
        if not node.data:
            return

        # Записываем в план действий только пакеты!
        if node.data.get("is_package"):
            pkg_key = node.data.get("key")
            pkg_name = node.data.get("pkg_name", pkg_key)
            installed_map = self.system_state.get("installed", {})
            is_installed = (pkg_name in installed_map) or (pkg_key in installed_map)

            effective_action = action_type
            if action_type in ["uninstall", "reinstall"] and not is_installed:
                effective_action = "none"
            elif action_type == "install" and is_installed:
                effective_action = "reinstall"

            if pkg_key:
                self.app_ref.actions[pkg_key] = effective_action
            action_type = effective_action
        elif node.data.get("is_folder"):
            node.data["folder_action"] = action_type

        marker = "[ ]"
        if action_type == "install":
            marker = "[+]"
        elif action_type == "reinstall":
            marker = "[↻]"
        elif action_type == "uninstall":
            marker = "[-]"

        current_label = str(node.label)
        for old_m in ["[ ]", "[+]", "[↻]", "[-]"]:
            if current_label.startswith(old_m):
                node.label = f"{marker}{current_label[3:]}"
                break

        for child in node.children:
            self._set_action_recursive(child, action_type)

    def on_key(self, event) -> None:
        """Перехват клавиш на уровне виджета дерева."""
        if event.key == "space":
            self.handle_space_press()
            event.prevent_default()
        elif event.key in ["right", "left"]:
            self.handle_left_right_keys(event.key)
            event.prevent_default()
