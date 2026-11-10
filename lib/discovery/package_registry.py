"""
Package registry storing discovered packages and units.
"""
import os
from typing import Any, Dict, List, Optional
from lib.discovery.directory_crawler import DirectoryCrawler
from lib.discovery.manifest_parser import ManifestParser
from lib.discovery.name_collision_resolver import NameCollisionResolver
from lib.discovery.package_cache_manager import PackageCacheManager


class PackageRegistry:
    """Реестр пакетов: хранение, индексация, кэширование и поиск."""

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
        self.packages[pkg_namespace] = package_data
        self.resolver.register_package(pkg_namespace, name)
        return pkg_namespace

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

    def get_folder_desc(self, folder_path: str) -> str:
        """Возвращает описание папки из её манифеста, если оно задано."""
        normalized = folder_path.strip("/").replace(os.sep, "/")
        if normalized in self.folders:
            return self.folders[normalized].get("desc", "")
        # Поиск по совпадению базового каталога или конца пути
        for f_ns, f_meta in self.folders.items():
            if f_ns == normalized or f_ns.endswith(f"/{normalized}"):
                return f_meta.get("desc", "")
        return ""

    def load_from_cache(self) -> bool:
        """Загружает базу пакетов из кэша packages.json."""
        data = self.cache_manager.load_cache()
        if not data or "packages" not in data:
            return False

        self.packages.clear()
        self.folders.clear()
        self.resolver.clear()
        if "folders" in data and isinstance(data["folders"], dict):
            self.folders.update(data["folders"])

        for namespace, pkg_data in data["packages"].items():
            self.register(pkg_data, namespace)
        return len(self.packages) > 0

    def save_to_cache(self) -> bool:
        """Сохраняет текущий реестр в кэш packages.json."""
        return self.cache_manager.save_cache(self.packages)

    def scan_directories(self, search_roots: List[str], force_rescan: bool = False) -> int:
        """
        Обходит директории и наполняет реестр.
        Манифесты во вложенных папках задают desc.
        Пустые манифесты валидны. Папки без манифеста игнорируются.
        """
        if not force_rescan and self.load_from_cache():
            return len(self.packages)

        self.packages.clear()
        self.folders.clear()
        self.resolver.clear()

        crawler = DirectoryCrawler(search_roots)
        discovered = crawler.crawl_all()

        for namespace, manifest_path in discovered.items():
            try:
                parsed = self.parser.parse_file(manifest_path)
                folder_desc = parsed.get("desc") or parsed.get("description") or ""
                if not folder_desc and parsed.get("is_multi_package"):
                    pkgs = parsed.get("packages", {})
                    dir_name = os.path.basename(os.path.dirname(manifest_path))
                    if dir_name in pkgs:
                        folder_desc = pkgs[dir_name].get("desc") or pkgs[dir_name].get("description") or ""
                    elif len(pkgs) == 1:
                        single_p = next(iter(pkgs.values()))
                        folder_desc = single_p.get("desc") or single_p.get("description") or ""

                base_dir = parsed.get("base_dir") or os.path.dirname(os.path.abspath(manifest_path))

                self.folders[namespace] = {
                    "desc": folder_desc,
                    "base_dir": base_dir,
                    "manifest_path": manifest_path,
                }

                # Если манифест пустой или предназначен только для описания папки
                if parsed.get("is_folder_only"):
                    continue

                if parsed.get("is_multi_package"):
                    for sub_name, sub_pkg in parsed.get("packages", {}).items():
                        if namespace.endswith(f"/{sub_name}") or namespace == sub_name:
                            sub_ns = namespace
                        else:
                            sub_ns = f"{namespace}/{sub_name}"
                        self.register(sub_pkg, sub_ns)
                else:
                    self.register(parsed, namespace)
            except Exception as err:
                print(f"⚠️ Ошибка загрузки манифеста {manifest_path}: {err}")

        # Сохраняем в кэш
        self.save_to_cache()
        return len(self.packages)

    def load_legacy_manifest(self, manifest_path: str) -> None:
        """Поддержка прямой загрузки одиночного manifest.json или дерева includes."""
        abs_path = os.path.abspath(manifest_path)
        base_dir = os.path.dirname(abs_path)
        parsed = self.parser.parse_file(abs_path)

        if parsed.get("is_multi_package"):
            for pkg_name, pkg_data in parsed.get("packages", {}).items():
                self.register(pkg_data, pkg_name)
            for inc in parsed.get("includes", []):
                inc_path = os.path.join(base_dir, inc)
                if os.path.exists(inc_path):
                    self.load_legacy_manifest(inc_path)
        else:
            pkg_name = parsed["name"]
            self.register(parsed, pkg_name)
