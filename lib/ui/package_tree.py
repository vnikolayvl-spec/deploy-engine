#!/usr/bin/env python3
"""
Кастомный виджет интерактивного иерархического дерева пакетов.
Строит дерево строго по иерархии подкатегорий и пакетов, скрывает неактивные
подкатегории (active=False) и по умолчанию оставляет узлы дерева свернутыми.
"""
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from lib.state.state_repository import StateRepository


class InfrastructureTree(Tree):
    """Иерархическое дерево подкатегорий, пакетов и юнитов."""

    UNIT_ICONS = {
        "env": "🔐 ENV:",
        "unit": "⚙️ Служба:",
        "service": "⚙️ Служба:",
        "timer": "⏱️ Таймер:",
        "script": "📜 Скрипт:",
        "data": "💾 Данные:",
        "symlink": "🔗 Симлинк:",
    }

    def __init__(self, engine, app_instance, **kwargs):
        super().__init__("Инфраструктура пакетов", **kwargs)
        self.engine = engine
        self.app_ref = app_instance
        state_data = StateRepository().get_state()
        installed = state_data.get("installed", {}) or state_data.get("installed_packages", {})
        self.system_state = {"installed_packages": installed, "installed": installed}

    @staticmethod
    def _ensure_branch(root_struct: dict, folder_path: str) -> dict:
        """Создает или возвращает ветку подкатегории в промежуточном словаре дерева."""
        parts = [p for p in folder_path.split("/") if p and p != "."]
        curr = root_struct
        built_parts = []
        for part in parts:
            built_parts.append(part)
            curr = curr["folders"].setdefault(
                part,
                {
                    "folders": {},
                    "packages": {},
                    "desc": "",
                    "active": True,
                    "order": 100,
                    "full_path": "/".join(built_parts),
                },
            )
        return curr

    def on_mount(self) -> None:
        """Построение свернутого по умолчанию дерева подкатегорий и пакетов."""
        self.root.expand()
        tree_structure = {
            "folders": {},
            "packages": {},
            "desc": "",
            "active": True,
            "order": 100,
            "full_path": "",
        }

        # 1. Регистрируем все подкатегории из реестра (включая их статус active и desc)
        folders_map = getattr(self.engine, "folders", {})
        for folder_path, f_info in sorted(folders_map.items()):
            curr = self._ensure_branch(tree_structure, folder_path)
            if f_info.get("desc"):
                curr["desc"] = f_info["desc"]
            if "active" in f_info:
                curr["active"] = bool(f_info["active"])
            if "order" in f_info:
                curr["order"] = int(f_info["order"])

        # 2. Размещаем активные пакеты в соответствующие подкатегории согласно их folder_path
        for reg_key, p_info in sorted(self.engine.packages.items()):
            if p_info.get("is_alias") or not p_info.get("active", True):
                continue
            curr = self._ensure_branch(tree_structure, p_info.get("folder_path", ""))
            pkg_name = p_info.get("name", reg_key.split("/")[-1])
            curr["packages"][pkg_name] = (reg_key, p_info)

        # 3. Рекурсивно монтируем узлы (по умолчанию все папки и пакеты свернуты)
        self._mount_directory_branch(self.root, tree_structure)

    def _mount_directory_branch(self, parent_node: TreeNode, branch_dict: dict) -> None:
        """Монтирует ветку активных подкатегорий и пакетов в дерево (в свернутом виде)."""
        folders = branch_dict.get("folders", {})
        sorted_folders = sorted(folders.items(), key=lambda item: (item[1].get("order", 100), item[0]))

        for folder_name, f_node_data in sorted_folders:
            if not f_node_data.get("active", True):
                continue

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
            self._mount_directory_branch(folder_node, f_node_data)

        packages = branch_dict.get("packages", {})
        installed_map = self.system_state.get("installed", {})

        for pkg_name, (reg_key, p_info) in sorted(packages.items()):
            if not p_info.get("active", True):
                continue

            is_installed = (pkg_name in installed_map) or (reg_key in installed_map)
            desc = p_info.get("description") or p_info.get("desc") or ""
            desc_str = f" ({desc})" if desc else ""

            if is_installed:
                label = f"[ ] [bold green]🎁 Пакет: {pkg_name} [УСТАНОВЛЕН][/bold green]{desc_str}"
            else:
                label = f"[ ] 🎁 Пакет: {pkg_name}{desc_str}"

            pkg_node = parent_node.add(
                label,
                data={"key": reg_key, "pkg_name": pkg_name, "is_package": True, "is_folder": False},
            )
            self._mount_package_units(pkg_node, pkg_name, p_info)

    def _mount_package_units(self, pkg_node: TreeNode, pkg_name: str, p_info: dict) -> None:
        """Добавляет юниты пакета как дочерние элементы под узлом пакета."""
        for u_name, u_spec in sorted((p_info.get("units") or {}).items()):
            u_spec = u_spec or {}
            u_type = u_spec.get("type")
            if not u_type:
                if u_name.endswith((".sh", ".py")):
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

            icon = self.UNIT_ICONS.get(u_type, "📄 Файл:")
            u_desc = u_spec.get("desc", "")
            u_desc_str = f" ({u_desc})" if u_desc else ""
            pkg_node.add(
                f"[ ] {icon} {u_name}{u_desc_str}",
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
            elif node.parent and node.parent != self.root:
                self.select_node(node.parent)

    def handle_space_press(self) -> None:
        """Переключает статус действия для текущего пакета или папки через Пробел."""
        node = self.cursor_node
        if not node or not node.data:
            return

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
                next_action = "install" if current_action == "none" else "none"

            self._set_action_recursive(node, next_action)
            self.app_ref.render_live_preview()

        elif node.data.get("is_folder"):
            current_action = node.data.get("folder_action", "none")
            next_action = "install" if current_action == "none" else "none"
            node.data["folder_action"] = next_action
            self._set_action_recursive(node, next_action)
            self.app_ref.render_live_preview()

    def _set_action_recursive(self, node: TreeNode, action_type: str) -> None:
        """Рекурсивно меняет маркеры узлов и записывает в actions только пакеты."""
        if not node.data:
            return

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

        markers = {"install": "[+]", "reinstall": "[↻]", "uninstall": "[-]"}
        marker = markers.get(action_type, "[ ]")
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
