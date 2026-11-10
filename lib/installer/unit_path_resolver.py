"""
Resolver for unit file paths and filesystem permissions.
"""
import os
from typing import Any, Dict, Optional, Tuple
from deploy_config import (
    DATA_PREFIX,
    ENV_PATH,
    ENV_PREFIX,
    STATE_DIR,
    SYS_BIN,
    SYS_SYSTEMD,
)
from lib.core.deploy_engine_error import DeployEngineError


class UnitPathResolver:
    """Определение исходных и системных путей, прав доступа и типов юнитов."""

    def __init__(self, base_packages_dir: str = "."):
        self.base_packages_dir = base_packages_dir

    def resolve(
        self,
        pkg_name: str,
        unit_name: str,
        unit_spec: Optional[Dict[str, Any]] = None,
        pkg_base_dir: Optional[str] = None,
    ) -> Tuple[str, str, int, str]:
        """
        Возвращает кортеж: (src_path, dest_path, mode, unit_type).
        """
        unit_spec = unit_spec or {}
        unit_type = unit_spec.get("type")

        # Определение типа юнита по расширению или имени, если не задан явно
        if not unit_type:
            if unit_name.endswith(".sh") or unit_name.endswith(".py"):
                unit_type = "script"
            elif unit_name.endswith(".service") or unit_name.endswith(".timer"):
                unit_type = "unit"
            elif unit_name.endswith(".env") or unit_name == "deploy.env":
                unit_type = "env"
            elif unit_spec.get("is_link") or unit_spec.get("symlink"):
                unit_type = "symlink"
            else:
                unit_type = "file"

        # Исходный путь
        file_src_rel = unit_spec.get("src", unit_name)
        if pkg_base_dir:
            src_path = os.path.join(pkg_base_dir, file_src_rel)
            # Если не найден в корне пакета, проверяем подпапку files/
            if not os.path.exists(src_path) and not unit_spec.get("symlink"):
                alt_path = os.path.join(pkg_base_dir, "files", file_src_rel)
                if os.path.exists(alt_path):
                    src_path = alt_path
        else:
            src_path = file_src_rel

        # Разрешение dest_path и mode
        if unit_type == "script":
            dest_path = unit_spec.get("target") or os.path.join(SYS_BIN, os.path.basename(unit_name))
            mode = unit_spec.get("mode", 0o755)

        elif unit_type in ["unit", "service", "timer"]:
            dest_path = unit_spec.get("target") or os.path.join(SYS_SYSTEMD, os.path.basename(unit_name))
            mode = unit_spec.get("mode", 0o644)

        elif unit_type == "env":
            dest_dir = os.path.join(ENV_PATH, f"{ENV_PREFIX}{pkg_name}")
            dest_name = os.path.basename(unit_name)
            # Если имя deploy.env, нормализуем к {pkg}.env
            if dest_name == "deploy.env":
                dest_name = f"{pkg_name}.env"
            dest_path = unit_spec.get("target") or os.path.join(dest_dir, dest_name)
            mode = unit_spec.get("mode", 0o600)

        elif unit_type == "data":
            # Хранилище постоянных / динамических данных пакета
            dest_dir = os.path.join(STATE_DIR, f"{DATA_PREFIX}{pkg_name}")
            dest_path = unit_spec.get("target") or os.path.join(dest_dir, os.path.basename(unit_name))
            mode = unit_spec.get("mode", 0o600)

        elif unit_type == "symlink":
            dest_path = unit_spec.get("target") or os.path.join(SYS_BIN, os.path.basename(unit_name))
            mode = 0o777

        elif unit_type == "file":
            dest_path = unit_spec.get("target")
            if not dest_path:
                dest_path = os.path.join("/etc", pkg_name, os.path.basename(unit_name))
            mode = unit_spec.get("mode", 0o644)

        else:
            raise DeployEngineError(f"Неизвестный тип юнита: {unit_type} в пакете {pkg_name}")

        return src_path, dest_path, mode, unit_type
