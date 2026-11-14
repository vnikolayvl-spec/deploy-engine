#!/usr/bin/env python3
"""
Кастомный виджет интерактивного иерархического дерева пакетов.
- Узлы папок и пакетов по умолчанию свернуты, раскрытие работает строго по стрелке Вправо.
- Обычные файлы добавляются как листья (add_leaf) без стрелочек разворота.
- Пробел меняет выбор только на пакете или папке (не срабатывает на вложенных файлах и не раскрывает пакет).
"""
import os
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from lib.state.state_repository import StateRepository


class InfrastructureTree(Tree):
    """Иерархическое дерево категорий, подкатегорий, пакетов и юнитов."""

    auto_expand = False

    UNIT_ICONS = {"env": "🔐 ENV:", "unit": "🔧 Служба:", "service": "🔧 Служба:", "timer": "⏰ Таймер:", "script": "📜 Скрипт:", "data": "💾 Данные:", "symlink": "🔗 Симлинк:"}

    def __init__(self, engine, app_instance, **kwargs):
        super().__init__("Инфраструктура пакетов", **kwargs)
        self.auto_expand, self.engine, self.app_ref = False, engine, app_instance
        self.system_state = {"installed_packages": {}, "installed": {}}
        self._refresh_system_state()

    def _refresh_system_state(self) -> None:
        state_repo = getattr(self.engine, "state_repo", None) or StateRepository()
        state_data = state_repo.get_state()
        installed = state_data.get("installed", {}) or state_data.get("installed_packages", {})
        self.system_state = {"installed_packages": installed, "installed": installed}

    @staticmethod
    def _ensure_branch(root_struct: dict, folder_path: str) -> dict:
        curr, built_parts = root_struct, []
        for part in [p for p in folder_path.split("/") if p and p != "."]:
            built_parts.append(part)
            curr = curr["folders"].setdefault(part, {"folders": {}, "packages": {}, "desc": "", "active": True, "order": 100, "full_path": "/".join(built_parts)})
        return curr

    def on_mount(self) -> None:
        self.rebuild_tree()

    def rebuild_tree(self) -> None:
        """Полная пересборка дерева при смене режима Sandbox или целевой ОС."""
        self._refresh_system_state()
        self.clear()
        self.root.expand()
        tree_structure = {"folders": {}, "packages": {}, "desc": "", "active": True, "order": 100, "full_path": ""}
        provider = getattr(self.engine, "provider", None)
        root_info = getattr(self.engine, "folders", {}).get(".", {})
        self.root.label = f"Инфраструктура пакетов ({root_info['desc']})" if (root_info and root_info.get("desc")) else "Инфраструктура пакетов"

        for folder_path, f_info in sorted(getattr(self.engine, "folders", {}).items()):
            if folder_path == ".":
                continue
            curr = self._ensure_branch(tree_structure, folder_path)
            for k in ("desc", "title", "name"):
                if f_info.get(k):
                    curr[k] = f_info[k]
            is_compat = self.engine.registry.is_folder_compatible(folder_path, provider) if hasattr(self.engine, "registry") else (provider.is_package_compatible(f_info) if provider else True)
            curr["active"] = bool(f_info.get("active", True)) and is_compat
            if "order" in f_info:
                curr["order"] = int(f_info["order"])

        for reg_key, p_info in sorted(self.engine.packages.items()):
            if p_info.get("is_alias") or p_info.get("is_external_manifest") or not p_info.get("active", True) or (hasattr(self.engine, "is_package_compatible") and not self.engine.is_package_compatible(p_info)):
                continue
            curr = self._ensure_branch(tree_structure, p_info.get("folder_path", ""))
            curr["packages"][p_info.get("name", reg_key.split("/")[-1])] = (reg_key, p_info)

        self._mount_directory_branch(self.root, tree_structure)

    def _mount_directory_branch(self, parent_node: TreeNode, branch_dict: dict) -> None:
        for folder_name, f_node_data in sorted(branch_dict.get("folders", {}).items(), key=lambda item: (item[1].get("order", 100), item[0])):
            if not f_node_data.get("active", True):
                continue
            desc_suffix = f" ({f_node_data['desc']})" if f_node_data.get("desc") else ""
            full_path = f_node_data.get("full_path") or folder_name
            display_title = f_node_data.get("title") or f_node_data.get("name") or folder_name
            folder_header = f"[bold cyan]📁 {display_title}[/bold cyan] [dim][{full_path}/][/dim]" if display_title != folder_name else f"[bold cyan]📁 {folder_name}/[/bold cyan]"
            folder_node = parent_node.add(f"[ ] {folder_header}{desc_suffix}", data={"key": f"folder:{full_path}", "folder_path": full_path, "is_folder": True, "is_package": False, "folder_action": "none"}, expand=False)
            self._mount_directory_branch(folder_node, f_node_data)

        installed_map = self.system_state.get("installed", {})
        markers = {"install": "[+]", "reinstall": "[↻]", "uninstall": "[-]"}
        for pkg_name, (reg_key, p_info) in sorted(branch_dict.get("packages", {}).items()):
            if not p_info.get("active", True):
                continue
            is_installed = (pkg_name in installed_map) or (reg_key in installed_map)
            desc = p_info.get("description") or p_info.get("desc") or ""
            desc_str = f" ({desc})" if desc else ""
            marker = markers.get(self.app_ref.actions.get(reg_key, "none"), "[ ]")
            label = f"{marker} [bold green]🎁 Пакет: {pkg_name} [УСТАНОВЛЕН][/bold green]{desc_str}" if is_installed else f"{marker} 🎁 Пакет: {pkg_name}{desc_str}"
            pkg_node = parent_node.add(label, data={"key": reg_key, "pkg_name": pkg_name, "is_package": True, "is_folder": False}, expand=False)
            self._mount_package_units(pkg_node, pkg_name, p_info, marker=marker, reg_key=reg_key, is_installed=is_installed)

    def _mount_package_units(self, pkg_node: TreeNode, pkg_name: str, p_info: dict, marker: str = "[ ]", reg_key: str = "", is_installed: bool = False) -> None:
        pkg_key = reg_key or pkg_name
        backup_plans = getattr(self.app_ref, "backup_plans", set())
        restore_plans = getattr(self.app_ref, "restore_plans", {})
        if is_installed:
            b_mark = "[✓]" if pkg_key in backup_plans else "[ ]"
            pkg_node.add_leaf(f"{b_mark} [bold cyan]💾 Создать бэкап[/bold cyan] (сохранить текущие data и .env)", data={"key": f"{pkg_key}:__backup__", "is_package": False, "is_folder": False, "is_backup_toggle": True, "pkg_key": pkg_key, "pkg_name": pkg_name})

        backup_count = self.engine.backup_manager.count_package_backups(pkg_name) if hasattr(self.engine, "backup_manager") else 0
        if backup_count > 0:
            r_mark = "[✓]" if restore_plans.get(pkg_key) else "[ ]"
            r_group = pkg_node.add(f"{r_mark} [bold magenta]🔄 Восстановить из бэкапа (доступно: {backup_count})[/bold magenta]", data={"key": f"{pkg_key}:__restore_group__", "is_package": False, "is_folder": False, "is_restore_group": True, "pkg_key": pkg_key, "pkg_name": pkg_name, "loaded": False}, expand=False)
            r_group.add_leaf("⏳ Загрузка списка бэкапов...", data={"is_placeholder": True})

        for u_name, u_spec in sorted((p_info.get("units") or {}).items()):
            u_spec = u_spec or {}
            u_type = u_spec.get("type") or ("script" if u_name.endswith((".sh", ".py")) else ("service" if u_name.endswith(".service") else ("timer" if u_name.endswith(".timer") else ("env" if (u_name.endswith(".env") or u_name == "deploy.env") else ("symlink" if u_spec.get("symlink") else "file")))))
            icon, u_desc = self.UNIT_ICONS.get(u_type, "📄 Файл:"), u_spec.get("desc", "")
            u_desc_str = f" ({u_desc})" if u_desc else ""
            node_data = {"key": f"{pkg_name}:{u_name}", "is_package": False, "is_folder": False, "is_env": u_type == "env", "pkg_name": pkg_name, "unit_name": u_name}
            if u_type == "env":
                preset_badge = " [bold yellow][настроен в env/][/bold yellow]" if os.path.isfile(self.engine.env_manager.get_local_preset_path(pkg_name)) else ""
                pkg_node.add(f"{marker} {icon} {u_name}{preset_badge}{u_desc_str}", data=node_data, expand=False)
            else:
                pkg_node.add_leaf(f"{marker} {icon} {u_name}{u_desc_str}", data=node_data)

    def _populate_restore_group(self, group_node: TreeNode) -> None:
        """Ленивая подгрузка списка архивов бэкапов при разворачивании узла восстановления."""
        if not group_node.data or group_node.data.get("loaded"):
            return
        pkg_name, pkg_key = group_node.data.get("pkg_name", ""), group_node.data.get("pkg_key", "")
        selected_arch = getattr(self.app_ref, "restore_plans", {}).get(pkg_key)
        group_node.remove_children()
        for b in (self.engine.backup_manager.list_package_backups(pkg_name) if hasattr(self.engine, "backup_manager") else []):
            arch = b["archive_name"]
            mark = "[✓]" if selected_arch == arch else "[ ]"
            tag = " [green](свежий)[/green]" if b.get("is_latest") else ""
            comm = f' | 💬 "{b["comment"]}"' if b.get("comment") else ""
            sz = self.engine.backup_manager._fmt_size(b.get("size_bytes", 0))
            group_node.add_leaf(f"{mark} #{b['index']} {arch}{tag} | v{b.get('version', '1.0.0')} | {sz}{comm}", data={"key": f"{pkg_key}:__restore__:{arch}", "is_package": False, "is_folder": False, "is_restore_item": True, "pkg_key": pkg_key, "pkg_name": pkg_name, "archive_name": arch})
        group_node.data["loaded"] = True

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        if event.node and event.node.data and event.node.data.get("is_restore_group"):
            self._populate_restore_group(event.node)

    def mark_env_configured(self, pkg_name: str) -> None:
        """Обновляет бейдж [настроен в env/] у узла ENV в дереве для указанного пакета."""
        def _walk(node: TreeNode) -> None:
            if node.data and node.data.get("is_env") and node.data.get("pkg_name") == pkg_name:
                cur_label = str(node.label)
                if "[настроен в env/]" not in cur_label:
                    node.label = f"{cur_label} [bold yellow][настроен в env/][/bold yellow]"
            for child in node.children:
                _walk(child)
        _walk(self.root)

    def _count_visible_descendants(self, node: TreeNode) -> int:
        if not node.is_expanded:
            return 0
        return sum(1 + self._count_visible_descendants(child) for child in node.children)

    def _perform_smart_scroll(self, node: TreeNode) -> None:
        node_line = getattr(node, "_line", -1)
        descendants_count = self._count_visible_descendants(node)
        viewport_height = self.scrollable_content_region.height or self.size.height
        if node_line < 0 or descendants_count <= 0 or viewport_height <= 1:
            return
        current_scroll_y = int(self.scroll_offset.y)
        bottom_needed = node_line + descendants_count
        if bottom_needed > current_scroll_y + viewport_height - 1:
            desired_scroll_y = bottom_needed - viewport_height + 1
            self.scroll_to(y=max(0, min(desired_scroll_y, node_line)), animate=False)

    def handle_left_right_keys(self, key_name: str) -> None:
        node = self.cursor_node
        if not node or not node.data:
            return
        if node.data.get("is_env") and key_name == "right":
            self.app_ref.open_env_editor(node)
            return

        is_container = node.data.get("is_package") or node.data.get("is_folder") or node.data.get("is_restore_group")
        if key_name == "right":
            if is_container:
                if node.data.get("is_restore_group"):
                    self._populate_restore_group(node)
                if not node.is_expanded:
                    node.expand()
                    self.call_after_refresh(self._perform_smart_scroll, node)
                elif node.children:
                    self.select_node(node.children[0])
        elif key_name == "left":
            if is_container and node.is_expanded:
                node.collapse()
            elif node.parent and node.parent != self.root:
                self.select_node(node.parent)

    def action_toggle_node(self) -> None:
        self.handle_space_press()

    def action_select_cursor(self) -> None:
        node = self.cursor_node
        if node and node.data and node.data.get("is_env"):
            self.app_ref.open_env_editor(node)
        else:
            self.handle_space_press()

    @staticmethod
    def _replace_prefix_marker(label_str: str, new_marker: str) -> str:
        for old_m in ("[ ]", "[✓]", "[+]", "[↻]", "[-]"):
            if label_str.startswith(old_m):
                return f"{new_marker}{label_str[len(old_m):]}"
        return label_str

    def handle_space_press(self) -> None:
        """Переключает выбор на пакете, папке, галочке бэкапа или конкретном архиве восстановления."""
        node = self.cursor_node
        if not node or not node.data:
            return

        if node.data.get("is_backup_toggle"):
            pkg_key = node.data["pkg_key"]
            if pkg_key in self.app_ref.backup_plans:
                self.app_ref.backup_plans.discard(pkg_key)
                node.label = self._replace_prefix_marker(str(node.label), "[ ]")
            else:
                self.app_ref.backup_plans.add(pkg_key)
                node.label = self._replace_prefix_marker(str(node.label), "[✓]")
            self.app_ref.render_live_preview()
            return

        if node.data.get("is_restore_group"):
            self._populate_restore_group(node)
            node.collapse() if node.is_expanded else (node.expand(), self.call_after_refresh(self._perform_smart_scroll, node))
            return

        if node.data.get("is_restore_item"):
            pkg_key, arch = node.data["pkg_key"], node.data["archive_name"]
            if self.app_ref.restore_plans.get(pkg_key) == arch:
                self.app_ref.restore_plans.pop(pkg_key, None)
            else:
                self.app_ref.restore_plans[pkg_key] = arch
            active_arch = self.app_ref.restore_plans.get(pkg_key)
            if node.parent:
                node.parent.label = self._replace_prefix_marker(str(node.parent.label), "[✓]" if active_arch else "[ ]")
                for sib in node.parent.children:
                    sib_arch = (sib.data or {}).get("archive_name")
                    sib.label = self._replace_prefix_marker(str(sib.label), "[✓]" if (sib_arch and sib_arch == active_arch) else "[ ]")
            self.app_ref.render_live_preview()
            return

        if node.data.get("is_package"):
            pkg_key, pkg_name = node.data["key"], node.data.get("pkg_name", node.data["key"])
            current_action = self.app_ref.actions.get(pkg_key, "none")
            installed_map = self.system_state.get("installed", {})
            next_action = ("reinstall" if current_action == "none" else ("uninstall" if current_action == "reinstall" else "none")) if (pkg_name in installed_map or pkg_key in installed_map) else ("install" if current_action == "none" else "none")
            self._set_action_recursive(node, next_action)
            self.app_ref.render_live_preview()
        elif node.data.get("is_folder"):
            next_action = "install" if node.data.get("folder_action", "none") == "none" else "none"
            node.data["folder_action"] = next_action
            self._set_action_recursive(node, next_action)
            self.app_ref.render_live_preview()

    def _set_action_recursive(self, node: TreeNode, action_type: str) -> None:
        if not node.data or node.data.get("is_backup_toggle") or node.data.get("is_restore_group") or node.data.get("is_restore_item"):
            return
        if node.data.get("is_package"):
            pkg_key, pkg_name = node.data.get("key"), node.data.get("pkg_name", node.data.get("key"))
            installed_map = self.system_state.get("installed", {})
            is_installed = (pkg_name in installed_map) or (pkg_key in installed_map)
            effective_action = "none" if (action_type in ["uninstall", "reinstall"] and not is_installed) else ("reinstall" if (action_type == "install" and is_installed) else action_type)
            if pkg_key:
                self.app_ref.actions[pkg_key] = effective_action
            action_type = effective_action
        elif node.data.get("is_folder"):
            node.data["folder_action"] = action_type

        marker = {"install": "[+]", "reinstall": "[↻]", "uninstall": "[-]"}.get(action_type, "[ ]")
        node.label = self._replace_prefix_marker(str(node.label), marker)
        for child in node.children:
            self._set_action_recursive(child, action_type)

    def on_key(self, event) -> None:
        if event.key == "space":
            self.handle_space_press()
            event.prevent_default()
            event.stop()
        elif event.key in ["right", "left"]:
            self.handle_left_right_keys(event.key)
            event.prevent_default()
            event.stop()
        elif event.key == "enter":
            self.action_select_cursor()
            event.prevent_default()
            event.stop()

