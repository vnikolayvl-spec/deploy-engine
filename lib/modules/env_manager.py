#!/usr/bin/env python3
import os
import sys
import re

def parse_env_file(filepath):
    """Аккуратно читает существующий .env файл в словарь"""
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

def process_env_unit(fname, file_info, src, dest):
    """
    Парсит исходный файл на наличие {{PROMPT:...}}, собирает variables из JSON,
    делает трехступенчатое слияние (Шаблон -> Сервер -> Промпт) и пишет в dest с правами 600.
    """
    print("\n" + "-"*50)
    print(f"🔐 Настройка окружения для: {fname}")
    print(f"📂 Путь назначения: {dest}")
    print("-"*50)

    # Шаг 1: Подгружаем базовые переменные из шаблона в репозитории (если он есть)
    final_vars = {}
    prompt_definitions = {}

    if src != "NOT_FOUND" and os.path.exists(src):
        try:
            with open(src, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()

                    # Ищем маркер {{PROMPT:Текст}}
                    match = re.search(r"\{\{PROMPT:(.*?)\}\}", val)
                    if match:
                        prompt_definitions[key] = match.group(1)
                    else:
                        final_vars[key] = val.strip('"').strip("'")
        except Exception as e:
            print(f"⚠️ Ошибка пре-парсинга шаблона {src}: {e}")

    # Шаг 2: Накатываем старую историю, которая уже была сохранена на сервере
    existing_vars = parse_env_file(dest)
    for key, val in existing_vars.items():
        final_vars[key] = val

    # Шаг 3: Накатываем переменные, жестко зашитые в manifest.json (если есть)
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
        else:
            final_vars[key] = val

    # Шаг 4: Запускаем интерактивные промпты для незаполненных секретов
    for key, notice in prompt_definitions.items():
        # Если переменной нет в истории сервера или манифесте — запрашиваем ввод
        if key not in final_vars or final_vars[key] == "":
            print(f"\n💬 [ПОДКАЗКА]: {notice}")
            try:
                user_input = input(f"👉 Введите значение для {key}: ").strip()
                final_vars[key] = user_input
            except (KeyboardInterrupt, EOFError):
                print("\n❌ Ввод отменен пользователем. Выход.")
                sys.exit(1)

    # Шаг 5: Записываем финальный результат в песочницу окружения
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            os.remove(dest)
            
        with open(dest, "w", encoding="utf-8") as f:
            f.write("# Автогенерация Deploy Engine. Настройки приложения.\n")
            for key, val in sorted(final_vars.items()):
                f.write(f'{key}="{val}"\n')
                
        os.chown(dest, 0, 0)
        os.chmod(dest, 0o600)
        print(f"✅ Файл конфигурации успешно скомпилирован (mode: 600).")
    except Exception as e:
        print(f"❌ Ошибка записи конфига в {dest}: {e}")
        sys.exit(1)

    return dest

