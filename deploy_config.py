#!/usr/bin/env python3
"""
Глобальные настройки системных путей для независимого деплоера.
"""

import os

SYS_BIN = "/usr/local/bin"          # Куда ставим скрипты
SYS_SYSTEMD = "/etc/systemd/system"  # Куда ставим службы systemd
VENV_PATH = "./.venv"               # Папка виртуального окружения

ENV_PATH = "/etc/default"       # Базовый системный каталог для секретов и окружения
ENV_PREFIX = "de_"              # Префикс безопасности для папок пакетов

STATE_DIR = "/var/lib"          # Базовый каталог для динамических данных (базы данных, хранилища)
DATA_PREFIX = "de_"             # Префикс для каталогов постоянных данных (/var/lib/de_{pkg})

# Корневая директория запуска deploy-engine
ENGINE_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Каталог пакетов по умолчанию
DEFAULT_PACKAGES_DIR = "./packages"
PACKAGES_DIR = os.getenv("DE_PACKAGES_DIR", DEFAULT_PACKAGES_DIR)

# Файл кэша пакетов
PACKAGES_CACHE_FILE = os.getenv("DE_PACKAGES_CACHE", "packages.json")

# Локальная папка в директории запуска (deploy-engine/env) для хранения предустановок .env
LOCAL_ENV_DIR = os.getenv("DE_LOCAL_ENV_DIR", os.path.join(ENGINE_ROOT_DIR, "env"))


