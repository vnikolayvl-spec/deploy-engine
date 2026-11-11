"""
Directory crawler for package and category hierarchy discovery.
"""
import os
from typing import Dict, List, Optional


class DirectoryCrawler:
    """
    Рекурсивный обход дерева папок для построения иерархии категорий и пакетов.
    Правила обхода:
    - Папки, в которых нет файла category.json или manifest.json, полностью игнорируются.
    - Папки с category.json или manifest.json регистрируются, и обход продолжается
      во вложенные подпапки, содержащие собственный манифест категории или пакета.
    """

    MANIFEST_FILES = ("category.json", "manifest.json")

    def __init__(self, search_roots: Optional[List[str]] = None):
        self.search_roots = search_roots or []

    @classmethod
    def _find_manifest_in_dir(cls, dir_path: str) -> Optional[str]:
        """Возвращает путь к файлу манифеста в папке (приоритет: manifest.json, затем category.json)."""
        for fname in ("manifest.json", "category.json"):
            candidate = os.path.join(dir_path, fname)
            if os.path.isfile(candidate):
                return candidate
        return None

    def crawl_directory(self, root_dir: str) -> Dict[str, str]:
        """
        Рекурсивно обходит root_dir по дереву папок с манифестами.
        Возвращает словарь {относительный_путь_папки: абсолютный_путь_к_манифесту}.
        """
        discovered: Dict[str, str] = {}
        abs_root = os.path.abspath(root_dir)

        if not os.path.exists(abs_root) or not os.path.isdir(abs_root):
            return discovered

        for current_dir, subdirs, _ in os.walk(abs_root, topdown=True):
            manifest_path = self._find_manifest_in_dir(current_dir)
            if manifest_path:
                rel_path = os.path.relpath(current_dir, abs_root)
                namespace = rel_path.replace(os.sep, "/") if rel_path != "." else "."
                discovered[namespace] = manifest_path

            # Игнорируем папки, в которых нет ни manifest.json, ни category.json
            subdirs[:] = sorted([
                d for d in subdirs
                if not d.startswith(".") and self._find_manifest_in_dir(os.path.join(current_dir, d)) is not None
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
