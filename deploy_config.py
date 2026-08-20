#!/usr/bin/env python3
"""
Глобальные настройки системных путей для независимого деплоера.
"""

SYS_BIN = "/usr/local/bin"          # Куда ставим скрипты
SYS_SYSTEMD = "/etc/systemd/system"  # Куда ставим службы systemd
VENV_PATH = "./.venv"               # Папка виртуального окружения

ENV_PATH = "/etc/default"       # Базовый системный каталог для секретов и окружения
ENV_PREFIX = "de_"              # Префикс безопасности для папок пакетов

