#!/usr/bin/env bash
# ==============================================================================
# deploy-engine.sh: Системный CLI лаунчер для пакета deploy-engine
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
NC='\033[0m'

ENV_FILE="/etc/default/de_deploy-engine/deploy-engine.env"
FILES_DIR="/opt/de_deploy-engine/files"

# Фолбек для локального автономного запуска из каталога репозитория
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$FILES_DIR" ] && [ -d "${SCRIPT_DIR}/../files" ]; then
    FILES_DIR="$(cd "${SCRIPT_DIR}/../files" && pwd)"
fi

if [ ! -f "$ENV_FILE" ] && [ -f "${FILES_DIR}/app.env" ]; then
    ENV_FILE="${FILES_DIR}/app.env"
elif [ ! -f "$ENV_FILE" ] && [ -f "${SCRIPT_DIR}/../deploy.env" ]; then
    ENV_FILE="${SCRIPT_DIR}/../deploy.env"
fi

if [ -e "${FILES_DIR}/deploy.py" ] && [ ! -r "${FILES_DIR}/deploy.py" ]; then
    echo -e "${RED}❌ Ошибка доступа к ${FILES_DIR}/deploy.py (Permission denied).${NC}" >&2
    echo -e "👉 Выполните: sudo chmod -R a+rX /opt/de_deploy-engine && sudo xattr -rc /opt/de_deploy-engine 2>/dev/null || true" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}❌ Ошибка: python3 не найден в системе. Установите python3.${NC}" >&2
    exit 1
fi

export DE_CONFIG_PATH="${DE_CONFIG_PATH:-$ENV_FILE}"
exec python3 "${FILES_DIR}/deploy.py" "$@"
