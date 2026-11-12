"""
Directory crawler for package and category hierarchy discovery.
"""
import os
from typing import Dict, List, Optional


class DirectoryCrawler:
    """
    Рекурсивный обход дерева папок для построения иерархии категорий и пакетов.
    Правила обхода:
    - Для описания категорий используется строго category.json (необязателен, если достаточно имени папки).
    - Для описания пакетов используется строго manifest.json.
    - Промежуточные папки без category.json автоматически обходятся, если внутри них на любой глубине есть пакеты или подкатегории.
    """

    MANIFEST_FILES = ("category.json", "manifest.json")
    IGNORED_DIRS = {"__pycache__", "node_modules", "venv", ".venv", "files", "data", "env", ".git", ".idea", ".vscode"}

    def __init__(self, search_roots: Optional[List[str]] = None):
        self.search_roots = search_roots or []

    @classmethod
    def _is_ignored_dir(cls, dirname: str) -> bool:
        return dirname.startswith(".") or dirname in cls.IGNORED_DIRS

    @classmethod
    def _find_manifest_in_dir(cls, dir_path: str) -> Optional[str]:
        """Возвращает путь к manifest.json или category.json в папке."""
        for fname in ("manifest.json", "category.json"):
            candidate = os.path.join(dir_path, fname)
            if os.path.isfile(candidate):
                return candidate
        return None

    @classmethod
    def _has_manifests_in_subtree(cls, dir_path: str) -> bool:
        """Проверяет, есть ли в данной папке или её подпапках хотя бы один manifest.json или category.json."""
        if cls._find_manifest_in_dir(dir_path) is not None:
            return True
        try:
            for _, subdirs, filenames in os.walk(dir_path, topdown=True):
                if "manifest.json" in filenames or "category.json" in filenames:
                    return True
                subdirs[:] = [d for d in subdirs if not cls._is_ignored_dir(d)]
        except OSError:
            return False
        return False

    def crawl_directory(self, root_dir: str) -> Dict[str, str]:
        """
        Рекурсивно обходит root_dir по дереву папок любой вложенности.
        Возвращает словарь {относительный_путь: абсолютный_путь_к_файлу}.
        Если в папке есть и category.json, и manifest.json, оба регистрируются.
        """
        discovered: Dict[str, str] = {}
        abs_root = os.path.abspath(root_dir)

        if not os.path.exists(abs_root) or not os.path.isdir(abs_root):
            return discovered

        for current_dir, subdirs, _ in os.walk(abs_root, topdown=True):
            rel_path = os.path.relpath(current_dir, abs_root)
            namespace = rel_path.replace(os.sep, "/") if rel_path != "." else "."

            cat_path = os.path.join(current_dir, "category.json")
            pkg_path = os.path.join(current_dir, "manifest.json")

            if os.path.isfile(cat_path) and os.path.isfile(pkg_path):
                if namespace != ".":
                    discovered[f"{namespace}#category"] = cat_path
                discovered[namespace] = pkg_path
            elif os.path.isfile(pkg_path):
                discovered[namespace] = pkg_path
            elif os.path.isfile(cat_path):
                discovered[namespace] = cat_path

            subdirs[:] = sorted([
                d for d in subdirs
                if not self._is_ignored_dir(d) and self._has_manifests_in_subtree(os.path.join(current_dir, d))
            ])

        return discovered

    def crawl_all(self) -> Dict[str, str]:
        """Обходит все зарегистрированные поисковые пути."""
        all_discovered: Dict[str, str] = {}
        for root in self.search_roots:
            if os.path.exists(root):
                found = self.crawl_directory(root)
                all_discovered.update(found)
        return all_discovered
