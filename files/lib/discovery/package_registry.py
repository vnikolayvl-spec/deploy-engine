"""
Package registry storing discovered packages, category/subcategory metadata, and units.
Categories use strictly category.json (optional if only folder name is needed); packages use manifest.json.
"""
import os
from typing import Any, Dict, List, Optional
from lib.discovery.category_manifest_parser import CategoryManifestParser
from lib.discovery.directory_crawler import DirectoryCrawler
from lib.discovery.manifest_parser import ManifestParser
from lib.discovery.name_collision_resolver import NameCollisionResolver
from lib.discovery.package_cache_manager import PackageCacheManager


class PackageRegistry:
    """Реестр пакетов и вложенных категорий: хранение, индексация, кэширование и поиск."""

    def __init__(self, cache_file: str = "packages.json"):
        self.packages: Dict[str, Dict[str, Any]] = {}
        self.folders: Dict[str, Dict[str, Any]] = {}
        self.resolver = NameCollisionResolver()
        self.parser = ManifestParser()
        self.category_parser = CategoryManifestParser()
        self.cache_manager = PackageCacheManager(cache_file)

    def register(self, package_data: Dict[str, Any], namespace: Optional[str] = None) -> str:
        """Регистрирует нормализованный пакет в реестре."""
        name = package_data["name"]
        pkg_namespace = namespace or name
        package_data["namespace"] = pkg_namespace
        if "folder_path" not in package_data:
            package_data["folder_path"] = os.path.dirname(pkg_namespace) if "/" in pkg_namespace else ""
        if "active" not in package_data:
            package_data["active"] = True
        self.packages[pkg_namespace] = package_data
        self.resolver.register_package(pkg_namespace, name)
        return pkg_namespace

    def register_folder(self, folder_path: str, folder_info: Dict[str, Any]) -> None:
        """Регистрирует метаданные категории/подкатегории (title, name, desc, active, order, platforms, meta)."""
        norm_path = "." if folder_path in ("", ".") else folder_path.strip("/")
        existing = self.folders.get(norm_path, {})
        raw_active = folder_info.get("active") if "active" in folder_info else folder_info.get("enabled")
        if raw_active is None and "active" in existing:
            active = bool(existing["active"])
        else:
            active = CategoryManifestParser.parse_bool(raw_active, default=True)

        desc = str(folder_info.get("desc") or folder_info.get("description") or existing.get("desc") or "").strip()
        base_dir = str(folder_info.get("base_dir") or existing.get("base_dir") or "")
        default_name = os.path.basename(os.path.abspath(base_dir or ".")) if norm_path == "." else os.path.basename(norm_path)
        name = str(folder_info.get("name") or existing.get("name") or default_name).strip() or default_name
        title = str(folder_info.get("title") or folder_info.get("name") or existing.get("title") or name).strip() or default_name

        self.folders[norm_path] = {
            "type": "category",
            "name": name,
            "title": title,
            "desc": desc,
            "description": desc,
            "active": active,
            "platforms": list(folder_info.get("platforms") or existing.get("platforms") or []),
            "order": int(folder_info.get("order", existing.get("order", 100))),
            "meta": dict(folder_info.get("meta") or existing.get("meta") or {}),
            "base_dir": base_dir,
            "folder_path": "" if norm_path == "." else norm_path,
        }

    def _ensure_ancestor_folders(self, folder_path: str, root_dir: str = "") -> None:
        """Автоматически регистрирует все родительские папки в цепочке пути (читая category.json при наличии)."""
        if not folder_path or folder_path == ".":
            return
        parts = [p for p in folder_path.split("/") if p and p != "."]
        built: List[str] = []
        for part in parts:
            built.append(part)
            rel_folder = "/".join(built)
            if rel_folder in self.folders:
                continue
            cand_dir = os.path.join(root_dir, *built) if root_dir else ""
            cat_path = os.path.join(cand_dir, "category.json") if cand_dir else ""
            if cat_path and os.path.isfile(cat_path):
                try:
                    self.register_folder(rel_folder, self.category_parser.parse_file(cat_path))
                    continue
                except Exception:
                    pass
            self.register_folder(
                rel_folder,
                {"name": part, "title": part, "desc": "", "active": True, "order": 100, "base_dir": cand_dir},
            )

    def is_folder_active(self, folder_path: str) -> bool:
        """Проверяет, активна ли сама категория и все ее родительские категории."""
        if not folder_path or folder_path == ".":
            root_info = self.folders.get(".")
            return bool(root_info.get("active", True)) if root_info else True
        parts = [p for p in folder_path.split("/") if p and p != "."]
        curr_parts: List[str] = []
        for part in parts:
            curr_parts.append(part)
            prefix = "/".join(curr_parts)
            f_info = self.folders.get(prefix)
            if f_info is not None and not f_info.get("active", True):
                return False
        return True

    def is_folder_compatible(self, folder_path: str, provider: Any) -> bool:
        """Проверяет активность и совместимость с ОС по всей цепочке родительских категорий."""
        if not self.is_folder_active(folder_path):
            return False
        if not folder_path or folder_path == "." or provider is None:
            return True
        parts = [p for p in folder_path.split("/") if p and p != "."]
        curr_parts: List[str] = []
        for part in parts:
            curr_parts.append(part)
            prefix = "/".join(curr_parts)
            f_info = self.folders.get(prefix)
            if f_info is not None and not provider.is_package_compatible(f_info):
                return False
        return True

    def get(self, query: str) -> Dict[str, Any]:
        target_namespace = self.resolver.resolve(query)
        return self.packages[target_namespace]

    def has(self, query: str) -> bool:
        try:
            self.resolver.resolve(query)
            return True
        except Exception:
            return False

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.packages)

    def load_from_cache(self) -> bool:
        """Загружает базу пакетов и категорий из кэша packages.json (с проверкой актуальности mtime)."""
        data = self.cache_manager.load_cache()
        if not data or data.get("version") != "2.3.0" or "packages" not in data or "folders" not in data:
            return False

        updated_at = float(data.get("updated_at") or 0)
        for item in list(data.get("folders", {}).values()) + list(data.get("packages", {}).values()):
            bdir = item.get("base_dir") if isinstance(item, dict) else None
            if bdir and os.path.isdir(bdir):
                for mf_name in ("manifest.json", "category.json"):
                    mf_path = os.path.join(bdir, mf_name)
                    if os.path.isfile(mf_path) and os.path.getmtime(mf_path) > updated_at:
                        return False

        self.packages.clear()
        self.folders.clear()
        self.resolver.clear()
        for folder_path, folder_data in data.get("folders", {}).items():
            self.register_folder(folder_path, folder_data)
        for namespace, pkg_data in data["packages"].items():
            self._ensure_ancestor_folders(pkg_data.get("folder_path", ""))
            self.register(pkg_data, namespace)
        return len(self.packages) > 0 or len(self.folders) > 0

    def save_to_cache(self) -> bool:
        return self.cache_manager.save_cache(self.packages, version="2.3.0", folders_index=self.folders)

    @staticmethod
    def _has_child_namespaces(ns: str, all_namespaces: List[str]) -> bool:
        if ns == ".":
            return any(other != "." for other in all_namespaces)
        prefix = f"{ns}/"
        return any(other.startswith(prefix) for other in all_namespaces)

    def scan_directories(
        self,
        search_roots: List[str],
        force_rescan: bool = False,
        save_cache: bool = True,
    ) -> int:
        """
        Обходит дерево директорий любой вложенности:
        - category.json задает параметры категории (необязателен, если достаточно имени папки).
        - manifest.json задает пакеты.
        """
        if not force_rescan and self.load_from_cache():
            return len(self.packages)

        self.packages.clear()
        self.folders.clear()
        self.resolver.clear()

        crawler = DirectoryCrawler(search_roots)
        discovered = crawler.crawl_all()
        clean_all_ns = list({k.split("#", 1)[0] for k in discovered.keys()})

        for raw_ns, manifest_path in sorted(discovered.items()):
            try:
                namespace = raw_ns.split("#", 1)[0]
                parsed = self.parser.parse_file(manifest_path)
                has_children = self._has_child_namespaces(namespace, clean_all_ns)
                norm_ns = "" if namespace == "." else namespace.strip("/")
                base_dir = parsed.get("base_dir", os.path.dirname(os.path.abspath(manifest_path)))
                root_dir = os.path.abspath(search_roots[0]) if search_roots else base_dir

                if os.path.basename(manifest_path) == "category.json" or parsed.get("is_category"):
                    parent_ns = os.path.dirname(norm_ns) if "/" in norm_ns else ""
                    if parent_ns:
                        self._ensure_ancestor_folders(parent_ns, root_dir)
                    self.register_folder(norm_ns or ".", parsed)
                    continue

                pkg_folder = "" if norm_ns == "" else (norm_ns if has_children else (os.path.dirname(norm_ns) if "/" in norm_ns else ""))
                if pkg_folder:
                    self._ensure_ancestor_folders(pkg_folder, root_dir)

                if parsed.get("is_multi_package"):
                    for sub_name, sub_pkg in parsed.get("packages", {}).items():
                        sub_pkg["folder_path"] = pkg_folder
                        reg_key = f"{pkg_folder}/{sub_name}" if pkg_folder else sub_name
                        self.register(sub_pkg, reg_key)
                    for inc in parsed.get("includes", []):
                        inc_path = os.path.normpath(os.path.join(base_dir, inc))
                        if os.path.exists(inc_path):
                            self.load_legacy_manifest(inc_path, root_base_dir=root_dir)
                else:
                    parsed["folder_path"] = pkg_folder
                    pkg_name = parsed["name"]
                    reg_key = norm_ns if norm_ns else pkg_name
                    self.register(parsed, reg_key)

            except Exception as err:
                print(f"⚠️ Ошибка загрузки манифеста {manifest_path}: {err}")

        for folder_path in list(self.folders.keys()):
            if not self.is_folder_active(folder_path):
                self.folders[folder_path]["active"] = False
        for pkg in self.packages.values():
            if not self.is_folder_active(pkg.get("folder_path", "")):
                pkg["active"] = False

        if save_cache:
            self.save_to_cache()
        return len(self.packages)

    def load_legacy_manifest(self, manifest_path: str, root_base_dir: Optional[str] = None) -> None:
        """Поддержка прямой загрузки manifest.json или директории пакетов."""
        abs_path = os.path.abspath(manifest_path)
        if os.path.isdir(abs_path):
            self.scan_directories([abs_path], force_rescan=True, save_cache=False)
            return

        base_dir = os.path.dirname(abs_path)
        effective_root = root_base_dir or base_dir
        if root_base_dir is None:
            self.scan_directories([effective_root], force_rescan=True, save_cache=False)

        parsed = self.parser.parse_file(abs_path)
        rel_dir = os.path.relpath(base_dir, effective_root)
        norm_rel = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")

        if os.path.basename(abs_path) == "category.json" or parsed.get("is_category"):
            self.register_folder(norm_rel or ".", parsed)
            return

        pkg_folder = os.path.dirname(norm_rel) if "/" in norm_rel else ""
        if pkg_folder:
            self._ensure_ancestor_folders(pkg_folder, effective_root)

        if parsed.get("is_multi_package"):
            for pkg_name, pkg_data in parsed.get("packages", {}).items():
                if not self.has(pkg_name):
                    pkg_data["folder_path"] = pkg_folder
                    self.register(pkg_data, f"{pkg_folder}/{pkg_name}" if pkg_folder else pkg_name)
            for inc in parsed.get("includes", []):
                inc_path = os.path.normpath(os.path.join(base_dir, inc))
                if os.path.exists(inc_path):
                    self.load_legacy_manifest(inc_path, root_base_dir=effective_root)
        else:
            pkg_name = parsed["name"]
            if not self.has(pkg_name):
                parsed["folder_path"] = pkg_folder
                self.register(parsed, norm_rel if norm_rel else pkg_name)

    def register_external_manifest(self, manifest_path: str, pkg_key: str) -> bool:
        """Догружает внешний манифест из state.json только если пакет отсутствует в основном реестре запуска."""
        if self.has(pkg_key) or not manifest_path or not os.path.isfile(manifest_path):
            return self.has(pkg_key)
        try:
            abs_mf = os.path.abspath(manifest_path)
            parsed = self.parser.parse_file(abs_mf)
            short_name = pkg_key.split("/")[-1]
            cand = (parsed.get("packages", {}).get(short_name) or parsed.get("packages", {}).get(pkg_key)) if parsed.get("is_multi_package") else parsed
            if not isinstance(cand, dict) or cand.get("is_category"):
                return False
            cand = dict(cand, is_external_manifest=True, manifest_path=abs_mf, folder_path="")
            self.register(cand, pkg_key)
            return True
        except Exception:
            return False
