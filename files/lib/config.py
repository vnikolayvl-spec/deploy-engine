#!/usr/bin/env python3
"""
lib/config.py: Иерархическая загрузка конфигурации и двухрежимное разрешение путей Deploy Engine
по эталонному шаблону Python-пакетов (template-py):
1. Переменные окружения процесса (os.environ) — наивысший приоритет.
2. Пользовательский конфиг (--config <path> или DE_CONFIG_PATH).
3. Системный конфиг установленного пакета (/etc/default/de_deploy-engine/deploy-engine.env).
4. Локальный конфиг автономного запуска (<ENGINE_ROOT_DIR>/app.env).
5. Базовые значения по умолчанию (DEFAULT_CONFIG) с автоматическим переключением
   динамических путей (packages/, backup/, env/, packages.json) в /var/lib/de_deploy-engine/
   при работе в качестве установленного системного пакета.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Optional

ENGINE_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD_CONFIG_PATH = Path("/etc/default/de_deploy-engine/deploy-engine.env")
LOCAL_ENV_PATH = Path(ENGINE_ROOT_DIR) / "app.env"
PROD_DATA_DIR = "/var/lib/de_deploy-engine"

DEFAULT_CONFIG: Dict[str, str] = {
    "DE_SYS_BIN": "/usr/local/bin",
    "DE_SYS_SYSTEMD": "/etc/systemd/system",
    "DE_VENV_PATH": "./.venv",
    "DE_ENV_PATH": "/etc/default",
    "DE_ENV_PREFIX": "de_",
    "DE_STATE_DIR": "/var/lib",
    "DE_DATA_PREFIX": "de_",
    "DE_REMOTE_ENGINE_DIR": "/opt/de_deploy-engine",
}


def parse_env_file(filepath: str) -> Dict[str, str]:
    """Парсит env-файл, отсекает комментарии '#', кавычки и нераскрытые шаблоны {{PROMPT:...}}."""
    result: Dict[str, str] = {}
    if not filepath or not os.path.isfile(filepath):
        return result
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1].strip()
                if not key or val == "" or "{{PROMPT:" in val:
                    continue
                result[key] = val
    except Exception:
        pass
    return result


def _load_env_from_file(env_path: Path, target_env: Optional[Dict[str, str]] = None) -> None:
    """Загружает переменные из файла через setdefault, не перезаписывая уже заданные значения."""
    env_dict = target_env if target_env is not None else os.environ
    for key, val in parse_env_file(str(env_path)).items():
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
    """
    Определяет, запущен ли deploy-engine как установленный системный пакет:
    - существует /etc/default/de_deploy-engine/deploy-engine.env
    - существует /var/lib/de_deploy-engine
    - код запущен из /opt/de_deploy-engine
    - явно задан DE_CONFIG_PATH
    """
    env_src = env_map if env_map is not None else os.environ
    root_abs = os.path.abspath(engine_root or ENGINE_ROOT_DIR)
    cfg_path = prod_config_path or PROD_CONFIG_PATH
    return (
        cfg_path.is_file()
        or os.path.isdir(prod_data_dir)
        or root_abs.startswith("/opt/de_deploy-engine")
        or bool(env_src.get("DE_CONFIG_PATH"))
    )


def load_config(
    custom_config_path: Optional[str] = None,
    engine_root: Optional[str] = None,
    prod_config_path: Optional[Path] = None,
    prod_data_dir: str = PROD_DATA_DIR,
    env_map: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Иерархический загрузчик конфигурации Deploy Engine:
    1. Переменные окружения (env_map / os.environ)
    2. Пользовательский конфиг (--config или DE_CONFIG_PATH)
    3. Системный конфиг (/etc/default/de_deploy-engine/deploy-engine.env)
    4. Локальный конфиг (<engine_root>/app.env)
    5. DEFAULT_CONFIG + двухрежимное разрешение путей данных
    """
    root_dir = os.path.abspath(engine_root or ENGINE_ROOT_DIR)
    sys_cfg = prod_config_path or PROD_CONFIG_PATH
    loc_cfg = Path(root_dir) / "app.env"

    effective_env: Dict[str, str] = dict(env_map if env_map is not None else os.environ)
    cli_cfg = custom_config_path or effective_env.get("DE_CONFIG_PATH") or _extract_cli_config_arg()

    if cli_cfg:
        _load_env_from_file(Path(cli_cfg), effective_env)
    _load_env_from_file(sys_cfg, effective_env)
    _load_env_from_file(loc_cfg, effective_env)
    for k, v in DEFAULT_CONFIG.items():
        effective_env.setdefault(k, v)

    is_prod = is_deploy_engine_environment(
        engine_root=root_dir,
        prod_config_path=sys_cfg,
        prod_data_dir=prod_data_dir,
        env_map=effective_env,
    )

    default_data_dir = prod_data_dir if is_prod else root_dir
    data_dir = effective_env.get("DE_DATA_DIR") or default_data_dir
    default_pkgs_dir = os.path.join(data_dir, "packages") if is_prod else "./packages"
    pkgs_dir = effective_env.get("DE_PACKAGES_DIR") or default_pkgs_dir
    default_cache = os.path.join(data_dir, "packages.json") if is_prod else "packages.json"
    cache_file = effective_env.get("DE_PACKAGES_CACHE") or default_cache
    local_env_dir = effective_env.get("DE_LOCAL_ENV_DIR") or os.path.join(data_dir, "env")
    backup_dir = effective_env.get("DE_BACKUP_DIR") or os.path.join(data_dir, "backup")

    return {
        "IS_PROD": "true" if is_prod else "false",
        "SYS_BIN": effective_env["DE_SYS_BIN"],
        "SYS_SYSTEMD": effective_env["DE_SYS_SYSTEMD"],
        "VENV_PATH": effective_env["DE_VENV_PATH"],
        "ENV_PATH": effective_env["DE_ENV_PATH"],
        "ENV_PREFIX": effective_env["DE_ENV_PREFIX"],
        "STATE_DIR": effective_env["DE_STATE_DIR"],
        "DATA_PREFIX": effective_env["DE_DATA_PREFIX"],
        "ENGINE_DATA_DIR": data_dir,
        "DEFAULT_PACKAGES_DIR": default_pkgs_dir,
        "PACKAGES_DIR": pkgs_dir,
        "PACKAGES_CACHE_FILE": cache_file,
        "LOCAL_ENV_DIR": local_env_dir,
        "BACKUP_DIR": backup_dir,
        "DEFAULT_REMOTE_ENGINE_DIR": effective_env["DE_REMOTE_ENGINE_DIR"],
    }


# Инициализация глобальных настроек при импорте модуля (с инжекцией в os.environ)
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
ENGINE_DATA_DIR = _ACTIVE_CFG["ENGINE_DATA_DIR"]
DEFAULT_PACKAGES_DIR = _ACTIVE_CFG["DEFAULT_PACKAGES_DIR"]
PACKAGES_DIR = _ACTIVE_CFG["PACKAGES_DIR"]
PACKAGES_CACHE_FILE = _ACTIVE_CFG["PACKAGES_CACHE_FILE"]
LOCAL_ENV_DIR = _ACTIVE_CFG["LOCAL_ENV_DIR"]
BACKUP_DIR = _ACTIVE_CFG["BACKUP_DIR"]
DEFAULT_REMOTE_ENGINE_DIR = _ACTIVE_CFG["DEFAULT_REMOTE_ENGINE_DIR"]
