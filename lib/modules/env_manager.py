#!/usr/bin/env python3
import os
import sys
import re
import stat

def parse_env_file(filepath):
    """Аккуратно читает существующий .env файл в словарь."""
    env_data = {}
    if not os.path.exists(filepath):
        return env_data
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                env_data[key.strip()] = val.strip().strip('"').strip("'")
    except Exception as e:
        print(f"⚠️ Предупреждение: Не удалось прочитать старый файл конфига {filepath}: {e}")
    return env_data


def _load_template_vars(src, final_vars, prompt_definitions):
    """Шаг 1: Подгружает базовые переменные и промпты из исходного шаблона."""
    if src == "NOT_FOUND" or not os.path.exists(src):
        return

    try:
        with open(src, "r", encoding="utf-8") as f:
            for line in f:
                raw_line = line.strip()
                if not raw_line or raw_line.startswith("#") or "=" not in raw_line:
                    continue
                
                key, val = raw_line.split("=", 1)
                key = key.strip()
                val = val.strip()

                # Ищем маркер {{PROMPT:Текст подсказки}}
                match = re.search(r"\{\{PROMPT:(.*?)\}\}", val)
                if match:
                    prompt_definitions[key] = match.group(1)
                    final_vars[key] = ""  # Инициализируем пустым для Шага 4
                else:
                    final_vars[key] = val.strip('"').strip("'")
    except Exception as e:
        print(f"⚠️ Ошибка пре-парсинга шаблона {src}: {e}")


def _merge_manifest_variables(file_info, final_vars, prompt_definitions):
    """Шаг 3: Накатывает переменные, жестко зашитые в manifest.json."""
    variables_cfg = file_info.get("variables", {})
    for key, cfg in variables_cfg.items():
        if isinstance(cfg, str):
            val = cfg
        else:
            val = cfg.get("value", "")
            if cfg.get("notice"):
                prompt_definitions[key] = cfg.get("notice")

        if val == "prompt":
            if key not in prompt_definitions:
                prompt_definitions[key] = f"Введите значение для {key}"
            final_vars[key] = final_vars.get(key, "")
        else:
            final_vars[key] = val


def _ask_interactive_prompt(key, notice):
    """Безопасно запрашивает ввод у пользователя через TTY или стандартный stdin."""
    print(f"\n💬 [ПОДКАЗКА]: {notice}")
    try:
        # Пытаемся читать напрямую из TTY, чтобы UI-сессии (наподобие curses) не ломали ввод
        sys.stdout.write(f"👉 Введите значение для {key}: ")
        sys.stdout.flush()
        with open("/dev/tty", "r") as tty:
            return tty.readline().strip()
    except Exception:
        # Фолбэк на стандартный input(), если /dev/tty недоступен (например, в тестах или пайплайнах)
        try:
            return input().strip()
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Ввод отменен пользователем. Выход.")
            sys.exit(1)


def _write_final_env(dest, final_vars):
    """Шаг 5: Компилирует финальный файл, выставляет права 600 и владельца root."""
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            os.remove(dest)

        with open(dest, "w", encoding="utf-8") as f:
            f.write("# Автогенерация Deploy Engine. Настройки приложения.\n")
            for key, val in sorted(final_vars.items()):
                f.write(f'{key}="{val}"\n')

        # Пытаемся сменить владельца на root:root (сработает только под sudo)
        try:
            os.chown(dest, 0, 0)
        except PermissionError:
            pass

        os.chmod(dest, 0o600)
        print(f"✅ Файл конфигурации успешно скомпилирован (mode: 600).")
    except Exception as e:
        print(f"❌ Ошибка записи конфига в {dest}: {e}")
        sys.exit(1)


def process_env_unit(fname, file_info, src, dest):
    """
    Основная точка входа для сборки юнитов типа 'env'.
    Делает трехступенчатое слияние (Шаблон -> История сервера -> Манифест)
    и запрашивает недостающие секреты в интерактивном режиме.
    """
    print("\n" + "-" * 50)
    print(f"🔐 Настройка окружения для: {fname}")
    print(f"📂 Путь назначения: {dest}")
    print("-" * 50)

    final_vars = {}
    prompt_definitions = {}

    # Шаг 1: Парсинг шаблона из репозитория
    _load_template_vars(src, final_vars, prompt_definitions)

    # Шаг 2: Накатывание существующей истории с сервера (state-compliance)
    existing_vars = parse_env_file(dest)
    for key, val in existing_vars.items():
        if val:  # Сохраняем старое значение, только если оно не пустое
            final_vars[key] = val

    # Шаг 3: Накатывание перегрузок из manifest.json
    _merge_manifest_variables(file_info, final_vars, prompt_definitions)

    # Шаг 4: Запуск интерактивных промптов для пустых переменных
    for key, notice in prompt_definitions.items():
        if not final_vars.get(key):
            user_value = _ask_interactive_prompt(key, notice)
            final_vars[key] = user_value

    # Шаг 5: Валидация директорий и запись на диск
    _write_final_env(dest, final_vars)

    return dest

