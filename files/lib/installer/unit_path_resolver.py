"""
Resolver for unit file paths and filesystem permissions with cross-platform provider support.
"""
import os
from typing import Any, Dict, Optional, Tuple
from lib.config import (
    DATA_PREFIX,
    ENV_PATH,
    ENV_PREFIX,
    STATE_DIR,
    SYS_BIN,
    SYS_SYSTEMD,
)
from lib.core.deploy_engine_error import DeployEngineError
from lib.providers.base_provider import BaseEnvironmentProvider
from lib.providers.systemd_to_plist_converter import SystemdToPlistConverter


class UnitPathResolver:
    """Определение исходных и системных путей, прав доступа и типов юнитов с учетом провайдера ОС."""

    def __init__(
        self,
        base_packages_dir: str = ".",
        provider: Optional[BaseEnvironmentProvider] = None,
    ):
        self.base_packages_dir = base_packages_dir
        self.provider = provider

    def get_active_paths(self) -> Dict[str, str]:
        """Возвращает системные пути из активного провайдера или дефолтные константы."""
        if self.provider:
            return self.provider.get_paths()
        return {
            "sys_bin": SYS_BIN,
            "sys_systemd": SYS_SYSTEMD,
            "env_path": ENV_PATH,
            "state_dir": STATE_DIR,
            "opt_dir": "/opt",
        }

    def resolve(
        self,
        pkg_name: str,
        unit_name: str,
        unit_spec: Optional[Dict[str, Any]] = None,
        pkg_base_dir: Optional[str] = None,
    ) -> Tuple[str, str, int, str]:
        """
        Возвращает кортеж: (src_path, dest_path, mode, unit_type).
        На macOS (или в песочнице macOS) для юнитов unit/service/timer целевой путь автоматически
        указывает на launchd .plist.
        """
        unit_spec = unit_spec or {}
        clean_name = unit_name.split(":")[-1]
        unit_type = unit_spec.get("type")

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

        paths = self.get_active_paths()
        sys_bin = paths["sys_bin"]
        sys_systemd = paths["sys_systemd"]
        env_path = paths["env_path"]
        state_dir = paths["state_dir"]
        opt_dir = paths.get("opt_dir", "/opt")

        base_dir_abs = os.path.abspath(pkg_base_dir or ".")
        root_dir_abs = os.path.abspath(unit_spec.get("root_dir") or os.path.dirname(base_dir_abs))
        context_vars = {
            "{{ROOT_DIR}}": root_dir_abs,
            "{{BASE_DIR}}": base_dir_abs,
            "{{SYS_BIN}}": sys_bin,
            "{{SYS_SYSTEMD}}": sys_systemd,
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

        # 2. Вычисление целевого пути (dest_path) и прав доступа (mode)
        custom_dest = unit_spec.get("dest") or unit_spec.get("target")
        raw_mode = unit_spec.get("mode")
        if isinstance(raw_mode, str):
            custom_mode: Optional[int] = int(raw_mode, 8)
        elif isinstance(raw_mode, int):
            custom_mode = raw_mode
        else:
            custom_mode = None

        use_plist = bool(self.provider and self.provider.uses_launchd_plist())

        if unit_type == "script":
            default_dest = os.path.join(sys_bin, os.path.basename(clean_name))
            default_mode = 0o755

        elif unit_type in ["unit", "service", "timer"]:
            if use_plist:
                plist_fname = SystemdToPlistConverter.get_plist_filename(pkg_name, clean_name)
                default_dest = os.path.join(sys_systemd, plist_fname)
                if custom_dest and ("/systemd/" in str(custom_dest) or "{{SYS_SYSTEMD}}" in str(custom_dest)):
                    custom_dest = None
            else:
                default_dest = os.path.join(sys_systemd, os.path.basename(clean_name))
            default_mode = 0o644

        elif unit_type == "env":
            dest_dir = os.path.join(env_path, f"{ENV_PREFIX}{pkg_name}")
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
            dest_dir = os.path.join(state_dir, f"{DATA_PREFIX}{pkg_name}")
            default_dest = os.path.join(dest_dir, os.path.basename(clean_name))
            default_mode = 0o600

        elif unit_type == "symlink":
            default_dest = os.path.join(sys_bin, os.path.basename(clean_name))
            default_mode = 0o777

        elif unit_type == "file":
            base_files_dir = os.path.join(opt_dir, f"de_{pkg_name}", "files")
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

        # Если активна песочница и в манифесте был задан абсолютный системный путь вне песочницы, перенаправляем его внутрь песочницы
        if self.provider and self.provider.is_sandbox and self.provider.sandbox_dir and custom_dest:
            sb_root = self.provider.sandbox_dir
            if os.path.isabs(dest_path) and not dest_path.startswith(sb_root):
                dest_path = os.path.join(sb_root, dest_path.lstrip("/"))

        mode = custom_mode if custom_mode is not None else default_mode
        return src_path, dest_path, mode, unit_type
