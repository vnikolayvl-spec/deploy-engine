"""
Directory crawler for package discovery.
"""
import json
import os
from typing import Dict, List, Optional


class DirectoryCrawler:
    """Рекурсивный обход директорий для поиска пакетов с терминальной остановкой на manifest.json."""

    def __init__(self, search_roots: Optional[List[str]] = None):
        self.search_roots = search_roots or []

    def crawl_directory(self, root_dir: str) -> Dict[str, str]:
        """
        Рекурсивно обходит root_dir.
        Только папки, содержащие manifest.json, регистрируются.
        Папки без манифеста игнорируются.
        Возвращает словарь {относительный_путь_неймспейс: абсолютный_путь_к_manifest}.
        """
        discovered: Dict[str, str] = {}
        abs_root = os.path.abspath(root_dir)

        if not os.path.exists(abs_root) or not os.path.isdir(abs_root):
            return discovered

        ignored_dirs = {
            "__pycache__", "node_modules", "dist", "build", ".venv",
            "venv", "env", ".git", ".tox", ".pytest_cache"
        }

        for current_dir, subdirs, files in os.walk(abs_root, topdown=True):
            # Игнорируем служебные и скрытые папки
            subdirs[:] = [
                d for d in subdirs
                if not d.startswith(".") and d not in ignored_dirs
            ]

            if "manifest.json" in files:
                manifest_path = os.path.join(current_dir, "manifest.json")
                rel_path = os.path.relpath(current_dir, abs_root)
                # Нормализуем неймспейс
                namespace = rel_path.replace(os.sep, "/") if rel_path != "." else os.path.basename(current_dir)
                discovered[namespace] = manifest_path

                # Проверяем, является ли манифест контейнерным (папка с includes или чисто описательный/пустой манифест папки)
                is_container = False
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if not content:
                            is_container = True
                        else:
                            raw = json.loads(content)
                            if "includes" in raw:
                                is_container = True
                            elif not raw.get("name") and not raw.get("packages") and not raw.get("units"):
                                is_container = True
                except Exception:
                    is_container = True

                # Для листовых пакетов не углубляемся во внутренние подкаталоги пакета
                if not is_container:
                    subdirs.clear()

        return discovered

    def crawl_all(self) -> Dict[str, str]:
        """Обходит все зарегистрированные поисковые пути."""
        all_discovered: Dict[str, str] = {}
        for root in self.search_roots:
            if os.path.exists(root):
                found = self.crawl_directory(root)
                all_discovered.update(found)
        return all_discovered
