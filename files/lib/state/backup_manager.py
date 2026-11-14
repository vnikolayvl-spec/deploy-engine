"""
Backup and restore manager for package dynamic data (data units & /var/lib/de_*) and environment configs (env units & /etc/default/de_*).
"""
import io
import json
import os
import shutil
import tarfile
import tempfile
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from lib.config import BACKUP_DIR, DATA_PREFIX, ENV_PREFIX, LOCAL_ENV_DIR
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.execution_context import ExecutionContext


class BackupManager:
    """Управление версионированными бэкапами (.tar.gz) данных и окружения пакетов."""

    def __init__(self, context: Optional[ExecutionContext] = None, provider=None, registry=None, path_resolver=None, state_repo=None, backup_root_dir: Optional[str] = None):
        self.context = context or ExecutionContext()
        self.provider, self.registry, self.path_resolver, self.state_repo = provider, registry, path_resolver, state_repo
        self.backup_root_dir = os.path.abspath(backup_root_dir or os.getenv("DE_BACKUP_DIR", BACKUP_DIR))

    def _to_logical_dest(self, phys_path: str) -> str:
        """Преобразует физический путь (с возможным префиксом песочницы) в канонический системный путь."""
        abs_p = os.path.abspath(phys_path)
        if self.provider and getattr(self.provider, "is_sandbox", False) and getattr(self.provider, "sandbox_dir", None):
            sb_root = os.path.abspath(self.provider.sandbox_dir)
            if abs_p.startswith(sb_root + os.sep):
                return "/" + os.path.relpath(abs_p, sb_root).replace(os.sep, "/")
        return abs_p

    def _to_physical_dest(self, logical_dest: str) -> str:
        """Преобразует канонический путь из backup_meta.json в физический путь активного провайдера/песочницы."""
        clean = logical_dest.strip()
        if self.provider and getattr(self.provider, "is_sandbox", False) and getattr(self.provider, "sandbox_dir", None):
            sb_root = os.path.abspath(self.provider.sandbox_dir)
            if os.path.isabs(clean) and not clean.startswith(sb_root):
                return os.path.join(sb_root, clean.lstrip("/"))
        return clean

    def collect_package_items(self, pkg_name: str) -> Tuple[str, str, List[Dict[str, Any]]]:
        """Собирает все существующие файлы и папки data и env пакета (включая кастомные dest из манифеста)."""
        pkg_info = self.registry.get(pkg_name) if (self.registry and self.registry.has(pkg_name)) else None
        canonical = pkg_info["name"] if pkg_info else pkg_name.split("/")[-1]
        state_entry = self.state_repo.get_installed_package(canonical) if self.state_repo else None
        version = str((pkg_info or {}).get("version") or (state_entry or {}).get("version") or "1.0.0")
        base_dir = (pkg_info or {}).get("base_dir", ".")
        paths = self.provider.get_paths() if self.provider else {"state_dir": "/var/lib", "env_path": "/etc/default"}

        candidates: List[Tuple[str, str, str]] = []
        if pkg_info and self.path_resolver:
            for u_name, u_spec in (pkg_info.get("units") or {}).items():
                try:
                    _, dest_path, _, u_type = self.path_resolver.resolve(canonical, u_name, u_spec, base_dir)
                    if u_type in ("data", "env"):
                        candidates.append((dest_path, u_type, u_name))
                except Exception:
                    continue

        std_data_dir, std_env_dir = os.path.join(paths["state_dir"], f"{DATA_PREFIX}{canonical}"), os.path.join(paths["env_path"], f"{ENV_PREFIX}{canonical}")
        for std_dir, cat in ((std_data_dir, "data"), (std_env_dir, "env")):
            if os.path.isdir(std_dir):
                candidates.extend(
                    (os.path.join(std_dir, e), cat, e)
                    for e in sorted(os.listdir(std_dir))
                    if not (e.startswith("install_") and e.endswith(".log"))
                )

        if state_entry:
            std_containers = {os.path.abspath(std_data_dir), os.path.abspath(std_env_dir)}
            for fpath in state_entry.get("files", []):
                if os.path.abspath(fpath) in std_containers:
                    continue
                if paths["state_dir"] in fpath or "/var/lib/" in fpath:
                    candidates.append((fpath, "data", os.path.basename(fpath)))
                elif paths["env_path"] in fpath or "/etc/default/" in fpath or fpath.endswith(".env"):
                    candidates.append((fpath, "env", os.path.basename(fpath)))

        items, seen_phys = [], set()
        for phys_path, category, unit_name in candidates:
            if not phys_path or not (os.path.exists(phys_path) or os.path.islink(phys_path)):
                continue
            abs_phys = os.path.abspath(phys_path)
            if abs_phys in seen_phys:
                continue
            seen_phys.add(abs_phys)
            st_mode = os.lstat(abs_phys).st_mode & 0o777
            idx = len(items)
            bname = os.path.basename(abs_phys.rstrip(os.sep)) or f"item_{idx}"
            items.append({
                "id": f"item_{idx}", "arcname": f"items/item_{idx}/{bname}", "category": category, "unit_name": unit_name,
                "phys_path": abs_phys, "logical_dest": self._to_logical_dest(abs_phys),
                "is_dir": os.path.isdir(abs_phys) and not os.path.islink(abs_phys),
                "mode": st_mode or (0o755 if os.path.isdir(abs_phys) else 0o600),
            })
        return canonical, version, items

    def resolve_targets(self, raw_targets: List[str], for_restore: bool = False) -> List[str]:
        """Преобразует список целей (с поддержкой мета-значения 'all') в список имен пакетов."""
        if not raw_targets or any(t.lower() == "all" for t in raw_targets):
            if for_restore:
                if not os.path.isdir(self.backup_root_dir): return []
                return sorted([d for d in os.listdir(self.backup_root_dir) if os.path.isdir(os.path.join(self.backup_root_dir, d)) and self.list_package_backups(d)])
            discovered: List[str] = list((self.state_repo.get_state().get("installed", {}) if self.state_repo else {}).keys())
            for pkg_info in (self.registry.packages.values() if self.registry else ()):
                pname = "" if pkg_info.get("is_alias") else pkg_info.get("name", "")
                if pname and pname not in discovered and self.collect_package_items(pname)[2]:
                    discovered.append(pname)
            return discovered
        return list(dict.fromkeys(raw_targets))

    def create_backup(self, pkg_name: str, comment: str = "") -> Dict[str, Any]:
        """Создает сжатый архив deploy-engine/backup/<pkg>/<timestamp>.tar.gz с backup_meta.json."""
        canonical, version, items = self.collect_package_items(pkg_name)
        if not items:
            raise DeployEngineError(f"У пакета '{canonical}' не найдено развернутых файлов data или env для бэкапа.")

        now = time.time()
        dt = datetime.fromtimestamp(now)
        ts_str = dt.strftime("%Y%m%d_%H%M%S")
        pkg_backup_dir = os.path.join(self.backup_root_dir, canonical)
        archive_name, suffix = f"{ts_str}.tar.gz", 1
        archive_path = os.path.join(pkg_backup_dir, archive_name)
        while os.path.exists(archive_path):
            archive_name = f"{ts_str}_{suffix}.tar.gz"
            archive_path = os.path.join(pkg_backup_dir, archive_name)
            suffix += 1

        meta = {
            "package": canonical, "version": version, "comment": (comment or "").strip(),
            "created_at": now, "timestamp": archive_name[:-7], "created_iso": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "distro_id": getattr(self.provider, "distro_id", "linux"),
            "items": [{k: v for k, v in it.items() if k != "phys_path"} for it in items],
        }
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Создание бэкапа '{canonical}' -> {archive_path} (элементов: {len(items)})")
            return {**meta, "archive_path": archive_path, "size_bytes": 0}

        os.makedirs(pkg_backup_dir, mode=0o700, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as tar:
            meta_bytes = json.dumps(meta, indent=2, ensure_ascii=False).encode("utf-8")
            ti = tarfile.TarInfo(name="backup_meta.json")
            ti.size, ti.mtime, ti.mode = len(meta_bytes), int(now), 0o600
            tar.addfile(ti, io.BytesIO(meta_bytes))
            for it in items:
                tar.add(it["phys_path"], arcname=it["arcname"], recursive=True)

        os.chmod(archive_path, 0o600)
        size_bytes = os.path.getsize(archive_path)
        comm = f' | 💬 "{meta["comment"]}"' if meta["comment"] else ""
        self.context.log(f"💾 Бэкап пакета '{canonical}' (v{version}) сохранен: {archive_path} ({self._fmt_size(size_bytes)}, путей: {len(items)}){comm}")
        return {**meta, "archive_path": archive_path, "size_bytes": size_bytes}

    def count_package_backups(self, pkg_name: str) -> int:
        """Быстрый подсчет количества архивов .tar.gz пакета без распаковки метаданных."""
        pkg_info = self.registry.get(pkg_name) if (self.registry and self.registry.has(pkg_name)) else None
        canonical = pkg_info["name"] if pkg_info else pkg_name.split("/")[-1]
        pkg_dir = os.path.join(self.backup_root_dir, canonical)
        if not os.path.isdir(pkg_dir):
            return 0
        return sum(1 for f in os.listdir(pkg_dir) if f.endswith(".tar.gz") and os.path.isfile(os.path.join(pkg_dir, f)))

    def list_package_backups(self, pkg_name: str) -> List[Dict[str, Any]]:
        """Возвращает отсортированный список бэкапов пакета (индекс 1 — самый свежий)."""
        pkg_info = self.registry.get(pkg_name) if (self.registry and self.registry.has(pkg_name)) else None
        canonical = pkg_info["name"] if pkg_info else pkg_name.split("/")[-1]
        pkg_dir = os.path.join(self.backup_root_dir, canonical)
        if not os.path.isdir(pkg_dir):
            return []
        records: List[Dict[str, Any]] = []
        for fname in os.listdir(pkg_dir):
            fpath = os.path.join(pkg_dir, fname)
            if fname.endswith(".tar.gz") and os.path.isfile(fpath):
                meta = self._read_archive_meta(fpath, canonical, fname)
                meta.update({"archive_name": fname, "archive_path": fpath, "size_bytes": os.path.getsize(fpath)})
                records.append(meta)
        records.sort(key=lambda r: (r.get("created_at", 0), r.get("archive_name", "")), reverse=True)
        for idx, rec in enumerate(records, start=1):
            rec["index"], rec["is_latest"] = idx, (idx == 1)
        return records

    def _read_archive_meta(self, archive_path: str, pkg_name: str, fname: str) -> Dict[str, Any]:
        """Считывает backup_meta.json из архива или формирует метаданные по файлу."""
        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                if "backup_meta.json" in tar.getnames():
                    f = tar.extractfile("backup_meta.json")
                    if f:
                        return json.loads(f.read().decode("utf-8"))
        except Exception:
            pass
        mtime = os.path.getmtime(archive_path)
        return {"package": pkg_name, "version": "1.0.0", "comment": "", "created_at": mtime, "timestamp": fname[:-7], "created_iso": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"), "items": []}

    def select_backup(self, pkg_name: str, selector: Optional[str] = None) -> Dict[str, Any]:
        """Выбирает бэкап: по умолчанию самый свежий [1], либо по номеру, штампу времени или имени файла."""
        backups = self.list_package_backups(pkg_name)
        if not backups:
            raise DeployEngineError(f"Для пакета '{pkg_name}' нет сохраненных бэкапов в {self.backup_root_dir}.")
        if not selector or str(selector).strip().lower() in ("latest", "last", "1"):
            return backups[0]
        sel = str(selector).strip()
        if sel.isdigit() and 1 <= int(sel) <= len(backups):
            return backups[int(sel) - 1]
        for b in backups:
            if sel in (b.get("timestamp"), b.get("archive_name")) or b.get("archive_name", "").startswith(sel):
                return b
        raise DeployEngineError(f"Бэкап '{selector}' для пакета '{pkg_name}' не найден. Доступно копий: {len(backups)}.")

    @staticmethod
    def _validate_tar_members(tar: tarfile.TarFile) -> None:
        """Защита от Path Traversal (Tar Slip): блокирует '..', абсолютные пути, спец-узлы и внешние ссылки."""
        for member in tar.getmembers():
            norm = os.path.normpath(member.name).replace("\\", "/")
            if norm.startswith("/") or norm.startswith("..") or "/../" in f"/{norm}/":
                raise DeployEngineError(f"Обнаружен небезопасный путь в архиве бэкапа (Path Traversal): {member.name}")
            if norm != "backup_meta.json" and not norm.startswith("items/"):
                raise DeployEngineError(f"Недопустимый элемент внутри архива бэкапа: {member.name}")
            if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                raise DeployEngineError(f"Архив содержит недопустимое системное устройство: {member.name}")
            if member.issym() or member.islnk():
                link_norm = os.path.normpath(member.linkname).replace("\\", "/")
                if os.path.isabs(link_norm) or link_norm.startswith(".."):
                    raise DeployEngineError(f"Архив содержит небезопасную внешнюю ссылку: {member.linkname}")

    def restore_backup(self, pkg_name: str, selector: Optional[str] = None) -> Dict[str, Any]:
        """Восстанавливает все пути data и env пакета из выбранного (или самого свежего) архива."""
        chosen = self.select_backup(pkg_name, selector)
        archive_path, canonical, items = chosen["archive_path"], chosen.get("package", pkg_name), chosen.get("items", [])
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Восстановление '{canonical}' из {archive_path} (элементов: {len(items)})")
            return {**chosen, "restored_paths": [self._to_physical_dest(i["logical_dest"]) for i in items]}

        restored_paths: List[str] = []
        with tempfile.TemporaryDirectory(prefix="de_restore_") as tmp_dir:
            with tarfile.open(archive_path, "r:gz") as tar:
                self._validate_tar_members(tar)
                tar.extractall(path=tmp_dir)
            for item in items:
                src_extracted = os.path.join(tmp_dir, item["arcname"])
                if not os.path.exists(src_extracted):
                    continue
                target_dest = self._to_physical_dest(item["logical_dest"])
                os.makedirs(os.path.dirname(target_dest), exist_ok=True)
                if item.get("is_dir") or os.path.isdir(src_extracted):
                    if os.path.exists(target_dest) and not os.path.isdir(target_dest):
                        os.unlink(target_dest)
                    shutil.copytree(src_extracted, target_dest, symlinks=True, dirs_exist_ok=True)
                else:
                    if os.path.isdir(target_dest):
                        shutil.rmtree(target_dest)
                    shutil.copy2(src_extracted, target_dest)
                if item.get("mode"):
                    try:
                        os.chmod(target_dest, int(item["mode"]))
                    except OSError:
                        pass
                restored_paths.append(target_dest)
                if item.get("category") == "env" and os.path.isfile(target_dest):
                    local_preset = os.path.join(LOCAL_ENV_DIR, f"{canonical}.env")
                    if os.path.isfile(local_preset):
                        shutil.copy2(target_dest, local_preset)

        comm = f' | 💬 "{chosen.get("comment")}"' if chosen.get("comment") else ""
        self.context.log(
            f"♻️ Пакет '{canonical}' восстановлен из бэкапа [{chosen['index']}] {chosen['archive_name']} (путей: {len(restored_paths)}){comm}"
        )
        return {**chosen, "restored_paths": restored_paths}

    def format_backups_list(self, targets: Optional[List[str]] = None) -> str:
        """Форматирует человекочитаемый список бэкапов для одного или нескольких пакетов."""
        pkgs = self.resolve_targets(targets or ["all"], for_restore=True)
        if not pkgs:
            return f"📭 В хранилище '{self.backup_root_dir}' пока нет сохраненных бэкапов."
        blocks: List[str] = []
        for pkg in pkgs:
            backups = self.list_package_backups(pkg)
            if not backups:
                blocks.append(f"📦 Пакет '{pkg}': нет сохраненных бэкапов.")
                continue
            lines = [f"📦 Доступные бэкапы пакета '{pkg}' ({os.path.join(self.backup_root_dir, pkg)}):"]
            for b in backups:
                tag = " (свежий)" if b.get("is_latest") else ""
                comm = f' | 💬 "{b["comment"]}"' if b.get("comment") else ""
                lines.append(f"  [{b['index']}] {b['archive_name']}{tag} | v{b.get('version', '1.0.0')} | {b.get('created_iso', '')} | {self._fmt_size(b.get('size_bytes', 0))}{comm}")
                lpaths = [it.get("logical_dest", "") for it in b.get("items", []) if it.get("logical_dest")]
                if lpaths:
                    lines.append(f"      Пути ({len(lpaths)}): {', '.join(lpaths)}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    @staticmethod
    def _fmt_size(size_bytes: int) -> str:
        return f"{size_bytes} B" if size_bytes < 1024 else (f"{size_bytes / 1024:.1f} KB" if size_bytes < 1048576 else f"{size_bytes / 1048576:.2f} MB")
