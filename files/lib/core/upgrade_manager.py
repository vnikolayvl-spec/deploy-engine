"""
Менеджер SemVer-обновлений установленных пакетов (deploy-engine upgrade [pkg|all]).
"""
from typing import Any, Dict, List, Optional
from lib.core.version_utils import version_status


class UpgradeManager:
    """Поиск устаревших пакетов по SemVer и их безопасное обновление с автобэкапом."""

    def __init__(self, engine):
        self.engine = engine

    def find_outdated(self, targets: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Возвращает список установленных пакетов, для которых в реестре есть более новая SemVer-версия.
        Если targets пуст или содержит 'all' — проверяются все установленные пакеты.
        """
        installed_map = self.engine.state_repo.get_state().get("installed", {})
        if not installed_map:
            return []

        check_all = not targets or any(str(t).strip().lower() == "all" for t in targets)
        requested_keys: List[str] = []
        if not check_all:
            for raw_t in targets or []:
                clean = str(raw_t).strip()
                if not clean:
                    continue
                if self.engine.registry.has(clean):
                    pkg = self.engine.registry.get(clean)
                    requested_keys.append(pkg["name"])
                else:
                    requested_keys.append(clean.split("/")[-1])

        outdated: List[Dict[str, Any]] = []
        for pkg_name, entry in sorted(installed_map.items()):
            if not check_all and pkg_name not in requested_keys and entry.get("namespace") not in requested_keys:
                continue
            lookup_key = entry.get("namespace") or pkg_name
            reg_pkg = None
            if self.engine.registry.has(lookup_key):
                reg_pkg = self.engine.registry.get(lookup_key)
            elif self.engine.registry.has(pkg_name):
                reg_pkg = self.engine.registry.get(pkg_name)
            if not reg_pkg:
                continue
            if not self.engine.provider.is_package_compatible(reg_pkg):
                continue

            inst_ver = str(entry.get("version", "0.0.0"))
            avail_ver = str(reg_pkg.get("version", "1.0.0"))
            if version_status(inst_ver, avail_ver) == "upgrade":
                outdated.append(
                    {
                        "package": reg_pkg["name"],
                        "namespace": reg_pkg["namespace"],
                        "installed_version": inst_ver,
                        "available_version": avail_ver,
                    }
                )
        return outdated

    def upgrade_packages(
        self,
        targets: Optional[List[str]] = None,
        auto_backup: bool = True,
    ) -> List[Dict[str, Any]]:
        """Обновляет только устаревшие установленные пакеты (с автобэкапом перед обновлением)."""
        outdated = self.find_outdated(targets)
        if not outdated:
            self.engine.context.log("✅ Все проверенные установленные пакеты уже на актуальных версиях.")
            return []

        self.engine.context.log(f"🔄 Найдено пакетов к обновлению ({len(outdated)}):")
        for item in outdated:
            self.engine.context.log(
                f"  • {item['package']}: v{item['installed_version']} -> v{item['available_version']}"
            )

        pkg_targets = [item["namespace"] for item in outdated]
        if auto_backup and not self.engine.context.dry_run and hasattr(self.engine, "backup_manager"):
            for item in outdated:
                try:
                    self.engine.backup_manager.create_backup(item["package"])
                except Exception as err:
                    self.engine.context.log(
                        f"❗ Предупреждение: не удалось создать автобэкап для '{item['package']}': {err}"
                    )

        self.engine.install_packages(pkg_targets)
        return outdated
