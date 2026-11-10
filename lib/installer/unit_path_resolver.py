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
        Поддерживает конвенции папок (files/, scripts/, systemd/),
        пользовательские пути dest/target и макросы {{SYS_BIN}}, {{SYS_SYSTEMD}}, {{BASE_DIR}}, {{ROOT_DIR}}.
        """
        unit_spec = unit_spec or {}
        clean_name = unit_name.split(":")[-1]
        unit_type = unit_spec.get("type")

        # Определение типа юнита по расширению или имени, если не задан явно
        if not unit_type:
            if unit_spec.get("is_link") or unit_spec.get("symlink"):
                unit_type = "symlink"
            elif clean_name.endswith(".sh") or clean_name.endswith(".py"):
                unit_type = "script"
            elif clean_name.endswith(".timer"):
                unit_type = "timer"
            elif clean_name.endswith(".service"):
                unit_type = "unit"
            elif clean_name.endswith(".env") or clean_name == "deploy.env":
                unit_type = "env"
            else:
                unit_type = "file"

        base_dir_abs = os.path.abspath(pkg_base_dir or ".")
        root_dir_abs = os.path.abspath(unit_spec.get("root_dir") or os.path.dirname(base_dir_abs))
        context_vars = {
            "{{ROOT_DIR}}": root_dir_abs,
            "{{BASE_DIR}}": base_dir_abs,
            "{{SYS_BIN}}": SYS_BIN,
            "{{SYS_SYSTEMD}}": SYS_SYSTEMD,
        }

        # 1. Вычисление исходного пути (src_path)
        if unit_type == "symlink":
            raw_src = str(unit_spec.get("symlink") or unit_spec.get("src") or clean_name)
            for marker, real_val in context_vars.items():
                raw_src = raw_src.replace(marker, real_val)
            src_path = raw_src
        else:
            file_src_rel = str(unit_spec.get("src") or clean_name)
            for marker, real_val in context_vars.items():
                file_src_rel = file_src_rel.replace(marker, real_val)

            if pkg_base_dir and not os.path.isabs(file_src_rel):
                lookup_paths = [
                    os.path.join(pkg_base_dir, file_src_rel),
                    os.path.join(pkg_base_dir, clean_name),
                    os.path.join(pkg_base_dir, "files", clean_name),
                    os.path.join(pkg_base_dir, "scripts", clean_name),
                    os.path.join(pkg_base_dir, "systemd", clean_name),
                ]
                src_path = lookup_paths[0]
                for candidate in lookup_paths:
                    if os.path.exists(candidate):
                        src_path = candidate
                        break
            else:
                src_path = file_src_rel

        # 2. Вычисление целевого пути (dest_path) и прав доступа (mode) по умолчанию
        custom_dest = unit_spec.get("dest") or unit_spec.get("target")
        raw_mode = unit_spec.get("mode")
        if isinstance(raw_mode, str):
            custom_mode: Optional[int] = int(raw_mode, 8)
        elif isinstance(raw_mode, int):
            custom_mode = raw_mode
        else:
            custom_mode = None

        if unit_type == "script":
            default_dest = os.path.join(SYS_BIN, os.path.basename(clean_name))
            default_mode = 0o755

        elif unit_type in ["unit", "service", "timer"]:
            default_dest = os.path.join(SYS_SYSTEMD, os.path.basename(clean_name))
            default_mode = 0o644

        elif unit_type == "env":
            dest_dir = os.path.join(ENV_PATH, f"{ENV_PREFIX}{pkg_name}")
            base_fname = os.path.basename(clean_name)
            if base_fname == "deploy.env":
                dest_name = f"{pkg_name}.env"
            elif "." in base_fname:
                dest_name = base_fname
            else:
                dest_name = "env"
            default_dest = os.path.join(dest_dir, dest_name)
            default_mode = 0o600

        elif unit_type == "data":
            dest_dir = os.path.join(STATE_DIR, f"{DATA_PREFIX}{pkg_name}")
            default_dest = os.path.join(dest_dir, os.path.basename(clean_name))
            default_mode = 0o600

        elif unit_type == "symlink":
            default_dest = os.path.join(SYS_BIN, os.path.basename(clean_name))
            default_mode = 0o777

        elif unit_type == "file":
            base_files_dir = os.path.join("/opt", f"de_{pkg_name}", "files")
            if clean_name == "files":
                default_dest = base_files_dir
            else:
                default_dest = os.path.join(base_files_dir, clean_name)
            default_mode = 0o644

        else:
            raise DeployEngineError(f"Неизвестный тип юнита: {unit_type} в пакете {pkg_name}")

        dest_path = str(custom_dest or default_dest)
        for marker, real_val in context_vars.items():
            dest_path = dest_path.replace(marker, real_val)

        mode = custom_mode if custom_mode is not None else default_mode
        return src_path, dest_path, mode, unit_type
