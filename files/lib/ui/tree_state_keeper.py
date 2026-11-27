"""
Хранитель состояния дерева TUI (Deploy Engine v3.0.0):
сохраняет и восстанавливает раскрытые ветки (категории, пакеты, группы бэкапов),
текущий узел курсора и позицию прокрутки при пересборке InfrastructureTree.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Set

if TYPE_CHECKING:
    from textual.widgets import Tree
    from textual.widgets.tree import TreeNode


class TreeStateKeeper:
    """Снимок и восстановление раскрытых узлов, курсора и прокрутки дерева Textual Tree."""

    @classmethod
    def capture(cls, tree: Tree) -> Dict[str, Any]:
        """Снимает текущее состояние дерева перед self.clear()."""
        expanded_keys: Set[str] = set()

        def _walk(node: TreeNode) -> None:
            data = getattr(node, "data", None)
            if isinstance(data, dict) and data.get("key") and getattr(node, "is_expanded", False):
                expanded_keys.add(str(data["key"]))
            for child in getattr(node, "children", []):
                _walk(child)

        root = getattr(tree, "root", None)
        if root is not None:
            _walk(root)

        cursor_key: Optional[str] = None
        cursor = getattr(tree, "cursor_node", None)
        if cursor is not None and isinstance(getattr(cursor, "data", None), dict):
            cursor_key = cursor.data.get("key")

        scroll_offset = getattr(tree, "scroll_offset", None)
        scroll_y = int(getattr(scroll_offset, "y", 0) or 0) if scroll_offset is not None else 0

        return {
            "expanded_keys": expanded_keys,
            "cursor_key": cursor_key,
            "scroll_y": scroll_y,
        }

    @classmethod
    def restore(
        cls,
        tree: Tree,
        snapshot: Optional[Dict[str, Any]],
        populate_restore_fn: Optional[Callable[[TreeNode], None]] = None,
    ) -> None:
        """Восстанавливает раскрытые узлы, курсор и прокрутку в пересобранном дереве."""
        if not snapshot:
            return
        expanded_keys: Set[str] = set(snapshot.get("expanded_keys") or set())
        cursor_key: Optional[str] = snapshot.get("cursor_key")
        scroll_y: int = int(snapshot.get("scroll_y") or 0)
        cursor_target: Optional[TreeNode] = None

        def _walk(node: TreeNode) -> None:
            nonlocal cursor_target
            data = getattr(node, "data", None)
            node_key = str(data.get("key")) if isinstance(data, dict) and data.get("key") else None
            if node_key and node_key in expanded_keys:
                if isinstance(data, dict) and data.get("is_restore_group") and callable(populate_restore_fn):
                    populate_restore_fn(node)
                try:
                    node.expand()
                except Exception:
                    pass
            if cursor_key and node_key == cursor_key:
                cursor_target = node
            for child in list(getattr(node, "children", [])):
                _walk(child)

        root = getattr(tree, "root", None)
        if root is not None:
            _walk(root)

        if cursor_target is not None:
            try:
                tree.select_node(cursor_target)
            except Exception:
                pass

        if scroll_y > 0 and hasattr(tree, "scroll_to"):
            def _apply_scroll() -> None:
                try:
                    tree.scroll_to(y=scroll_y, animate=False)
                except Exception:
                    pass

            if hasattr(tree, "call_after_refresh"):
                try:
                    tree.call_after_refresh(_apply_scroll)
                    return
                except Exception:
                    pass
            _apply_scroll()
