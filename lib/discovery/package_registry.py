"""
Package registry storing discovered packages, folder hierarchy metadata, and units.
"""
import os
from typing import Any, Dict, List, Optional
from lib.discovery.directory_crawler import DirectoryCrawler
from lib.discovery.manifest_parser import ManifestParser
from lib.discovery.name_collision_resolver import NameCollisionResolver
from lib.discovery.package_cache_manager import PackageCacheManager


class PackageRegistry:
    """Реестр пакетов и папок: хранение, индексация, кэширование и поиск."""

    def __init__(self, cache_file: str = "packages.json"):
        self.packages: Dict[str, Dict[str, Any]] = {}
        self.folders: Dict[str, Dict[str, Any]] = {}
        self.resolver = NameCollisionResolver()
        self.parser = ManifestParser()
        self.cache_manager = PackageCacheManager(cache_file)

    def register(self, package_data: Dict[str, Any], namespace: Optional[str] = None) -> str:
        """Регистрирует нормализованный пакет в реестре."""
        name = package_data["name"]
        pkg_namespace = namespace or name
        package_data["namespace"] = pkg_namespace
        if "folder_path" not in package_data:
            package_data["folder_path"] = os.path.dirname(pkg_namespace) if "/" in pkg_namespace else ""
        self.packages[pkg_namespace] = package_data
        self.resolver.register_package(pkg_namespace, name)
        return pkg_namespace

    def register_folder(self, folder_path: str, folder_info: Dict[str, Any]) -> None:
        """Регистрирует метаданные папки (включая desc) в иерархии дерева."""
        norm_path = "" if folder_path in ("", ".") else folder_path.strip("/")
        if not norm_path:
            return
        self.folders[norm_path] = {
            "name": folder_info.get("name") or os.path.basename(norm_path),
            "desc": folder_info.get("desc") or folder_info.get("description") or "",
            "base_dir": folder_info.get("base_dir", ""),
            "folder_path": norm_path,
        }

    def get(self, query: str) -> Dict[str, Any]:
        """Возвращает данные пакета по короткому имени или пространству имен."""
        target_namespace = self.resolver.resolve(query)
        return self.packages[target_namespace]

    def has(self, query: str) -> bool:
        """Проверяет наличие пакета."""
        try:
            self.resolver.resolve(query)
            return True
        except Exception:
            return False

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает все зарегистрированные пакеты."""
        return dict(self.packages)

    def load_from_cache(self) -> bool:
        """Загружает базу пакетов и папок из кэша packages.json."""
        data = self.cache_manager.load_cache()
        if not data or "packages" not in data or "folders" not in data:
            return False

        self.packages.clear()
        self.folders.clear()
        self.resolver.clear()
        for folder_path, folder_data in data.get("folders", {}).items():
            self.register_folder(folder_path, folder_data)
        for namespace, pkg_data in data["packages"].items():
            self.register(pkg_data, namespace)
        return len(self.packages) > 0 or len(self.folders) > 0

    def save_to_cache(self) -> bool:
        """Сохраняет текущий реестр пакетов и папок в кэш packages.json."""
        return self.cache_manager.save_cache(self.packages, folders_index=self.folders)

    @staticmethod
    def _has_child_namespaces(ns: str, all_namespaces: List[str]) -> bool:
        """Проверяет, есть ли у данной папки вложенные подпапки с манифестами."""
        if ns == ".":
            return any(other != "." for other in all_namespaces)
        prefix = f"{ns}/"
        return any(other.startswith(prefix) for other in all_namespaces)

    def scan_directories(self, search_roots: List[str], force_rescan: bool = False) -> int:
        """
        Обходит директории по дереву папок с manifest.json и наполняет реестр.
        """
        if not force_rescan and self.load_from_cache():
            return len(self.packages)

        self.packages.clear()
        self.folders.clear()
        self.resolver.clear()

        crawler = DirectoryCrawler(search_roots)
        discovered = crawler.crawl_all()
        all_ns = list(discovered.keys())

        for namespace, manifest_path in sorted(discovered.items()):
            try:
                parsed = self.parser.parse_file(manifest_path)
                has_children = self._has_child_namespaces(namespace, all_ns)
                norm_ns = "" if namespace == "." else namespace.strip("/")

                # 1. Если манифест относится только к папке (пустой {} или содержит только desc)
                if parsed.get("is_folder_only"):
                    if norm_ns:
                        self.register_folder(norm_ns, parsed)
                    continue

                # 2. Если у папки есть вложенные подпапки с манифестами, регистрируем саму папку
                if has_children and norm_ns:
                    self.register_folder(norm_ns, {
                        "name": os.path.basename(norm_ns),
                        "desc": parsed.get("desc", ""),
                        "base_dir": parsed.get("base_dir", ""),
                    })

                # Определяем родительскую папку для пакетов внутри этого манифеста
                if norm_ns == "":
                    pkg_folder = ""
                elif has_children:
                    pkg_folder = norm_ns
                else:
                    pkg_folder = os.path.dirname(norm_ns) if "/" in norm_ns else ""

                if parsed.get("is_multi_package"):
                    for sub_name, sub_pkg in parsed.get("packages", {}).items():
                        sub_pkg["folder_path"] = pkg_folder
                        reg_key = f"{pkg_folder}/{sub_name}" if pkg_folder else sub_name
                        self.register(sub_pkg, reg_key)
                else:
                    parsed["folder_path"] = pkg_folder
                    pkg_name = parsed["name"]
                    reg_key = norm_ns if norm_ns else pkg_name
                    self.register(parsed, reg_key)

            except Exception as err:
                print(f"⚠️ Ошибка загрузки манифеста {manifest_path}: {err}")

        self.save_to_cache()
        return len(self.packages)

    def load_legacy_manifest(self, manifest_path: str, root_base_dir: Optional[str] = None) -> None:
        """Поддержка прямой загрузки manifest.json с сохранением иерархии папок."""
        abs_path = os.path.abspath(manifest_path)
        base_dir = os.path.dirname(abs_path)
        effective_root = root_base_dir or base_dir

        # Сначала выполняем обход дерева папок от корневой директории манифеста
        if root_base_dir is None:
            self.scan_directories([effective_root], force_rescan=True)

        parsed = self.parser.parse_file(abs_path)
        rel_dir = os.path.relpath(base_dir, effective_root)
        norm_rel = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")

        if parsed.get("is_multi_package"):
            pkg_folder = os.path.dirname(norm_rel) if "/" in norm_rel else ""
            for pkg_name, pkg_data in parsed.get("packages", {}).items():
                if not self.has(pkg_name):
                    pkg_data["folder_path"] = pkg_folder
                    reg_key = f"{pkg_folder}/{pkg_name}" if pkg_folder else pkg_name
                    self.register(pkg_data, reg_key)
            for inc in parsed.get("includes", []):
                inc_path = os.path.normpath(os.path.join(base_dir, inc))
                if os.path.exists(inc_path):
                    inc_rel_dir = os.path.relpath(os.path.dirname(inc_path), effective_root).replace(os.sep, "/")
                    parent_folder = os.path.dirname(inc_rel_dir) if "/" in inc_rel_dir else ""
                    if parent_folder and parent_folder not in self.folders:
                        self.register_folder(parent_folder, {
                            "name": os.path.basename(parent_folder),
                            "desc": "",
                            "base_dir": os.path.join(effective_root, parent_folder),
                        })
                    self.load_legacy_manifest(inc_path, root_base_dir=effective_root)
        elif not parsed.get("is_folder_only"):
            pkg_name = parsed["name"]
            if not self.has(pkg_name):
                pkg_folder = os.path.dirname(norm_rel) if "/" in norm_rel else ""
                parsed["folder_path"] = pkg_folder
                reg_key = norm_rel if norm_rel else pkg_name
                self.register(parsed, reg_key)
        elif norm_rel:
            self.register_folder(norm_rel, parsed)
