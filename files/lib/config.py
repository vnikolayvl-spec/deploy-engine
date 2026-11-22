#!/usr/bin/env python3
"""
lib/config.py: Иерархическая загрузка конфигурации и кроссплатформенное разрешение путей Deploy Engine:
1. Переменные окружения процесса (os.environ) — наивысший приоритет.
2. Пользовательский конфиг (--config <path> или DE_CONFIG_PATH).
3. Системный конфиг (/etc/default/de_deploy-engine/deploy-engine.env или macOS user path).
4. Локальный конфиг автономного запуска (<ENGINE_ROOT_DIR>/app.env).
5. Платформенные пути (Linux / macOS root / macOS user) с маркером #AUTO# и мягкой обработкой PermissionError.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Set

ENGINE_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_CONFIG_PATH = Path("/etc/default/de_deploy-engine/deploy-engine.env")
LOCAL_ENV_PATH = Path(ENGINE_ROOT_DIR) / "app.env"
PROD_DATA_DIR = "/var/lib/de_deploy-engine"
AUTO_VALUE_MARKER = "#AUTO#"
_WARNED_PERMISSION_PATHS: Set[str] = set()

DEFAULT_CONFIG: Dict[str, str] = {
    "DE_SYS_BIN": "/usr/local/bin",
    "DE_SYS_SYSTEMD": "/etc/systemd/system",
    "DE_VENV_PATH": "./.venv",
    "DE_ENV_PATH": "/etc/default",
    "DE_ENV_PREFIX": "de_",
    "DE_STATE_DIR": "/var/lib",
    "DE_DATA_PREFIX": "de_",
    "DE_OPT_DIR": "/opt",
    "DE_REMOTE_ENGINE_DIR": "/opt/de_deploy-engine",
}


def is_auto_value(value: Optional[str]) -> bool:
    """Возвращает True, если значение является маркером автоопределения #AUTO#."""
    return (value or "").strip() == AUTO_VALUE_MARKER


def _should_suppress_stderr_warning() -> bool:
    """Подавляет текстовые предупреждения в stderr для машинного вывода (--json / completion)."""
    args = sys.argv[1:]
    return "--json" in args or "completion" in args


def _warn_permission_once(filepath: str) -> None:
    """Выводит однократное мягкое предупреждение при отсутствии прав на чтение системного .env."""
    norm = str(filepath)
    if norm in _WARNED_PERMISSION_PATHS:
        return
    _WARNED_PERMISSION_PATHS.add(norm)
    if not _should_suppress_stderr_warning():
        print(
            f"❗ Предупреждение: нет прав на чтение '{norm}' (используются доступные настройки; "
            "для чтения системной конфигурации запустите с sudo).",
            file=sys.stderr,
        )


def _safe_is_file(path: Path) -> Optional[bool]:
    """Безопасная проверка is_file(): возвращает None при PermissionError (с мягким предупреждением)."""
    try:
        return path.is_file()
    except PermissionError:
        _warn_permission_once(str(path))
        return None
    except OSError:
        return False


def _safe_is_dir(path: str) -> bool:
    """Безопасная проверка os.path.isdir() без падения на PermissionError."""
    try:
        return os.path.isdir(path)
    except PermissionError:
        _warn_permission_once(path)
        return True
    except OSError:
        return False


def get_platform_default_paths(
    platform_name: Optional[str] = None,
    is_root: Optional[bool] = None,
    home_dir: Optional[str] = None,
) -> Dict[str, str]:
    """Возвращает системные пути целевой ОС с учетом платформы (Linux / macOS) и прав root."""
    plat = (platform_name or sys.platform).lower()
    root = (hasattr(os, "geteuid") and os.geteuid() == 0) if is_root is None else bool(is_root)
    home = home_dir or os.path.expanduser("~")

    if plat == "darwin":
        if os.path.isdir("/opt/homebrew/bin") and (root or os.access("/opt/homebrew/bin", os.W_OK)):
            sys_bin = "/opt/homebrew/bin"
        elif root or os.access("/usr/local/bin", os.W_OK):
            sys_bin = "/usr/local/bin"
        else:
            sys_bin = os.path.join(home, ".local", "bin")
        if root:
            return {
                "DE_SYS_BIN": sys_bin,
                "DE_SYS_SYSTEMD": "/Library/LaunchDaemons",
                "DE_ENV_PATH": "/etc/default",
                "DE_STATE_DIR": "/var/lib",
                "DE_OPT_DIR": "/opt",
            }
        return {
            "DE_SYS_BIN": sys_bin,
            "DE_SYS_SYSTEMD": os.path.join(home, "Library", "LaunchAgents"),
            "DE_ENV_PATH": os.path.join(home, ".config", "deploy-engine", "default"),
            "DE_STATE_DIR": os.path.join(home, ".local", "state", "deploy-engine"),
            "DE_OPT_DIR": os.path.join(home, ".local", "opt"),
        }
    return {
        "DE_SYS_BIN": "/usr/local/bin",
        "DE_SYS_SYSTEMD": "/etc/systemd/system",
        "DE_ENV_PATH": "/etc/default",
        "DE_STATE_DIR": "/var/lib",
        "DE_OPT_DIR": "/opt",
    }


def parse_env_file(filepath: str) -> Dict[str, str]:
    """Парсит env-файл, отсекает комментарии, #AUTO#, нераскрытые {{PROMPT:...}} и мягко обрабатывает PermissionError."""
    result: Dict[str, str] = {}
    if not filepath:
        return result
    try:
        if not os.path.isfile(filepath):
            return result
        with open(filepath, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1].strip()
                if not key or val == "" or is_auto_value(val) or "{{PROMPT:" in val:
                    continue
                result[key] = val
    except PermissionError:
        _warn_permission_once(filepath)
    except Exception:
        pass
    return result


def _load_env_from_file(env_path: Path, target_env: Optional[Dict[str, str]] = None) -> None:
    """Загружает переменные из файла через setdefault, не перезаписывая уже заданные значения."""
    env_dict = target_env if target_env is not None else os.environ
    for key, val in parse_env_file(str(env_path)).items():
        if not is_auto_value(val):
            env_dict.setdefault(key, val)


def _extract_cli_config_arg(argv: Optional[list] = None) -> Optional[str]:
    """Извлекает путь из флага --config <path>, если он передан в аргументах командной строки."""
    args = argv if argv is not None else sys.argv[1:]
    for idx, token in enumerate(args):
        if token == "--config" and idx + 1 < len(args):
            return args[idx + 1]
        if token.startswith("--config="):
            return token.split("=", 1)[1]
    return None


def is_deploy_engine_environment(
    engine_root: Optional[str] = None,
    prod_config_path: Optional[Path] = None,
    prod_data_dir: str = PROD_DATA_DIR,
    env_map: Optional[Dict[str, str]] = None,
) -> bool:
    """Определяет, запущен ли deploy-engine как установленный системный пакет (безопасно к PermissionError)."""
    env_src = env_map if env_map is not None else os.environ
    root_abs = os.path.abspath(engine_root or ENGINE_ROOT_DIR)
    cfg_exists = _safe_is_file(prod_config_path or PROD_CONFIG_PATH)
    return (
        cfg_exists is True
        or cfg_exists is None
        or _safe_is_dir(prod_data_dir)
        or root_abs.startswith("/opt/de_deploy-engine")
        or bool(env_src.get("DE_CONFIG_PATH"))
    )


def _effective_non_auto(env_dict: Dict[str, str], key: str, fallback: str) -> str:
    """Возвращает значение ключа из env_dict, если оно не пустое и не равно #AUTO#."""
    raw = env_dict.get(key)
    cleaned = str(raw).strip() if raw is not None else ""
    return fallback if (not cleaned or is_auto_value(cleaned)) else cleaned


def load_config(
    custom_config_path: Optional[str] = None,
    engine_root: Optional[str] = None,
    prod_config_path: Optional[Path] = None,
    prod_data_dir: Optional[str] = None,
    env_map: Optional[Dict[str, str]] = None,
    platform_name: Optional[str] = None,
    is_root: Optional[bool] = None,
    home_dir: Optional[str] = None,
) -> Dict[str, str]:
    """Иерархический загрузчик конфигурации Deploy Engine с поддержкой #AUTO# и путей Linux/macOS."""
    root_dir = os.path.abspath(engine_root or ENGINE_ROOT_DIR)
    plat_defaults = get_platform_default_paths(platform_name=platform_name, is_root=is_root, home_dir=home_dir)
    default_sys_cfg = Path(plat_defaults["DE_ENV_PATH"]) / "de_deploy-engine" / "deploy-engine.env"
    if prod_config_path is not None:
        sys_cfg = prod_config_path
    elif platform_name is not None and platform_name.lower() != sys.platform.lower():
        sys_cfg = default_sys_cfg
    else:
        sys_cfg = PROD_CONFIG_PATH if _safe_is_file(PROD_CONFIG_PATH) in (True, None) else default_sys_cfg
    eff_prod_data = prod_data_dir if prod_data_dir is not None else os.path.join(plat_defaults["DE_STATE_DIR"], "de_deploy-engine")
    loc_cfg = Path(root_dir) / "app.env"

    effective_env: Dict[str, str] = {
        k: v for k, v in (env_map if env_map is not None else os.environ).items() if not is_auto_value(v)
    }
    cli_cfg = custom_config_path or effective_env.get("DE_CONFIG_PATH") or _extract_cli_config_arg()
    if cli_cfg:
        _load_env_from_file(Path(cli_cfg), effective_env)
    _load_env_from_file(sys_cfg, effective_env)
    _load_env_from_file(loc_cfg, effective_env)

    merged_defaults = {**DEFAULT_CONFIG, **plat_defaults}
    for k, v in merged_defaults.items():
        if is_auto_value(effective_env.get(k)) or not effective_env.get(k):
            effective_env[k] = v

    is_prod = is_deploy_engine_environment(
        engine_root=root_dir, prod_config_path=sys_cfg, prod_data_dir=eff_prod_data, env_map=effective_env
    )
    default_data_dir = eff_prod_data if is_prod else root_dir
    data_dir = _effective_non_auto(effective_env, "DE_DATA_DIR", default_data_dir)
    pkg_dir_names = ("packages", "deploy-packages", "deploy_packages")
    if is_prod:
        default_pkgs_dir = next(
            (os.path.join(data_dir, d) for d in pkg_dir_names if _safe_is_dir(os.path.join(data_dir, d))),
            os.path.join(data_dir, "packages"),
        )
    else:
        default_pkgs_dir = next(
            (f"./{d}" for d in pkg_dir_names if _safe_is_dir(os.path.join(data_dir, d))),
            "./packages",
        )
    default_venv = os.path.join(effective_env["DE_OPT_DIR"], "de_deploy-engine", "files", ".venv") if is_prod else "./.venv"
    return {
        "IS_PROD": "true" if is_prod else "false",
        "SYS_BIN": effective_env["DE_SYS_BIN"],
        "SYS_SYSTEMD": effective_env["DE_SYS_SYSTEMD"],
        "VENV_PATH": _effective_non_auto(effective_env, "DE_VENV_PATH", default_venv),
        "ENV_PATH": effective_env["DE_ENV_PATH"],
        "ENV_PREFIX": effective_env["DE_ENV_PREFIX"],
        "STATE_DIR": effective_env["DE_STATE_DIR"],
        "DATA_PREFIX": effective_env["DE_DATA_PREFIX"],
        "OPT_DIR": effective_env["DE_OPT_DIR"],
        "ENGINE_DATA_DIR": data_dir,
        "DEFAULT_PACKAGES_DIR": default_pkgs_dir,
        "PACKAGES_DIR": _effective_non_auto(effective_env, "DE_PACKAGES_DIR", default_pkgs_dir),
        "PACKAGES_CACHE_FILE": _effective_non_auto(
            effective_env, "DE_PACKAGES_CACHE", os.path.join(data_dir, "packages.json") if is_prod else "packages.json"
        ),
        "LOCAL_ENV_DIR": _effective_non_auto(effective_env, "DE_LOCAL_ENV_DIR", os.path.join(data_dir, "env")),
        "BACKUP_DIR": _effective_non_auto(effective_env, "DE_BACKUP_DIR", os.path.join(data_dir, "backup")),
        "DEFAULT_REMOTE_ENGINE_DIR": effective_env["DE_REMOTE_ENGINE_DIR"],
    }


_cli_cfg = _extract_cli_config_arg()
if _cli_cfg:
    _load_env_from_file(Path(_cli_cfg))
if os.getenv("DE_CONFIG_PATH"):
    _load_env_from_file(Path(os.environ["DE_CONFIG_PATH"]))
_load_env_from_file(PROD_CONFIG_PATH)
_load_env_from_file(LOCAL_ENV_PATH)

_ACTIVE_CFG = load_config()
IS_DEPLOY_ENGINE_ENV = _ACTIVE_CFG["IS_PROD"] == "true"
SYS_BIN = _ACTIVE_CFG["SYS_BIN"]
SYS_SYSTEMD = _ACTIVE_CFG["SYS_SYSTEMD"]
VENV_PATH = _ACTIVE_CFG["VENV_PATH"]
ENV_PATH = _ACTIVE_CFG["ENV_PATH"]
ENV_PREFIX = _ACTIVE_CFG["ENV_PREFIX"]
STATE_DIR = _ACTIVE_CFG["STATE_DIR"]
DATA_PREFIX = _ACTIVE_CFG["DATA_PREFIX"]
OPT_DIR = _ACTIVE_CFG["OPT_DIR"]
ENGINE_DATA_DIR = _ACTIVE_CFG["ENGINE_DATA_DIR"]
DEFAULT_PACKAGES_DIR = _ACTIVE_CFG["DEFAULT_PACKAGES_DIR"]
PACKAGES_DIR = _ACTIVE_CFG["PACKAGES_DIR"]
PACKAGES_CACHE_FILE = _ACTIVE_CFG["PACKAGES_CACHE_FILE"]
LOCAL_ENV_DIR = _ACTIVE_CFG["LOCAL_ENV_DIR"]
BACKUP_DIR = _ACTIVE_CFG["BACKUP_DIR"]
DEFAULT_REMOTE_ENGINE_DIR = _ACTIVE_CFG["DEFAULT_REMOTE_ENGINE_DIR"]
