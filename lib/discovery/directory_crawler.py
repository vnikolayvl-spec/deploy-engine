"""
Directory crawler for package and folder hierarchy discovery.
"""
import os
from typing import Dict, List, Optional


class DirectoryCrawler:
    """
    Рекурсивный обход дерева папок для построения иерархии пакетов.
    Правила обхода:
    - Папки, в которых нет файла manifest.json, полностью игнорируются.
    - Папки с manifest.json (включая пустой {} или содержащий только desc) регистрируются,
      и обход продолжается во вложенные подпапки, содержащие собственный manifest.json.
    """

    def __init__(self, search_roots: Optional[List[str]] = None):
        self.search_roots = search_roots or []

    def crawl_directory(self, root_dir: str) -> Dict[str, str]:
        """
        Рекурсивно обходит root_dir по дереву папок с manifest.json.
        Возвращает словарь {относительный_путь_папки: абсолютный_путь_к_manifest}.
        """
        discovered: Dict[str, str] = {}
        abs_root = os.path.abspath(root_dir)

        if not os.path.exists(abs_root) or not os.path.isdir(abs_root):
            return discovered

        for current_dir, subdirs, files in os.walk(abs_root, topdown=True):
            if "manifest.json" in files:
                manifest_path = os.path.join(current_dir, "manifest.json")
                rel_path = os.path.relpath(current_dir, abs_root)
                namespace = rel_path.replace(os.sep, "/") if rel_path != "." else "."
                discovered[namespace] = manifest_path

            # Игнорируем папки, в которых нет manifest.json
            subdirs[:] = sorted([
                d for d in subdirs
                if not d.startswith(".") and os.path.isfile(os.path.join(current_dir, d, "manifest.json"))
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
