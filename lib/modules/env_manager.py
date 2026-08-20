#!/usr/bin/env python3
import os
import sys

def parse_env_file(filepath):
    """Аккуратно читает существующий .env файл, возвращая словарь ключ-значение"""
    env_data = {}
    if not os.path.exists(filepath):
        return env_data
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Игнорируем комментарии и пустые строки
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                # Убираем возможные кавычки вокруг значения
                val = val.strip().strip('"').strip("'")
                env_data[key.strip()] = val
    except Exception as e:
        print(f"⚠️ Предупреждение: Не удалось прочитать старый файл конфига {filepath}: {e}")
    return env_data

def process_env_unit(fname, file_info, default_dest):
    """
    Обрабатывает юнит типа 'env': запрашивает prompt, делает умное слияние 
    с существующим файлом и перезаписывает его с правами 600.
    """
    dest = file_info.get("dest", default_dest)
    variables_cfg = file_info.get("variables", {})
    
    if not variables_cfg:
        return dest

    print("\n" + "-"*50)
    print(f"🔐 Настройка конфигурационного окружения для: {fname}")
    print(f"📂 Путь назначения: {dest}")
    print("-"*50)

    # 1. Собираем новые значения на основе манифеста и ввода пользователя
    computed_vars = {}
    for key, cfg in variables_cfg.items():
        # Если переменная объявлена старой плоской строкой, а не объектом
        if isinstance(cfg, str):
            val_type = cfg
            notice = ""
        else:
            val_type = cfg.get("value", "")
            notice = cfg.get("notice", "")

        if val_type == "prompt":
            if notice:
                print(f"\n💬 [ПОДКАЗКА]: {notice}")
            try:
                user_input = input(f"👉 Введите значение для {key}: ").strip()
                computed_vars[key] = user_input
            except (KeyboardInterrupt, EOFError):
                print("\n❌ Ввод отменен пользователем. Выход.")
                sys.exit(1)
        else:
            computed_vars[key] = val_type

    # 2. Читаем старые переменные, которые уже сохранены на сервере
    existing_vars = parse_env_file(dest)

    # 3. Интеллектуальный Upsert: обновляем старое новыми данными, чужие ключи не трогаем
    final_vars = existing_vars.copy()
    for key, val in computed_vars.items():
        final_vars[key] = val

    # 4. Записываем итоговый результат в песочницу
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        
        # Если файл существовал, удаляем его, чтобы сбросить старые небезопасные права
        if os.path.exists(dest):
            os.remove(dest)
            
        with open(dest, "w", encoding="utf-8") as f:
            for key, val in sorted(final_vars.items()):
                # Записываем в чистом системном формате КЛЮЧ="ЗНАЧЕНИЕ"
                f.write(f'{key}="{val}"\n')
                
        # Намертво закрываем права доступа: только чтение/запись для root
        os.chown(dest, 0, 0)
        os.chmod(dest, 0o600)
        print(f"✅ Файл конфигурации успешно обновлен и защищен (mode: 600).")
        
    except Exception as e:
        print(f"❌ Ошибка записи конфига в {dest}: {e}")
        sys.exit(1)

    return dest

