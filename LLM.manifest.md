# SYSTEM SPECIFICATION FOR LLM: Generating `manifest.json` for Deploy Engine

Этот документ представляет собой строгую техническую спецификацию для языковых моделей (LLM / AI-агентов) по созданию валидных файлов **`manifest.json`** и структуры папок пакетов для **Deploy Engine**.

---

## 1. Концептуальные правила и инварианты (CRITICAL RULES)

1. **Строгое назначение `manifest.json`:**
   - Файл `manifest.json` описывает **ТОЛЬКО пакет** (или набор пакетов через секцию `"packages"`).
   - **ЗАПРЕЩЕНО** использовать `manifest.json` для описания категорий/папок. Для категорий используется исключительно `category.json`.
   - **ЗАПРЕЩЕНО** добавлять в `manifest.json` вымышленные ключи вроде `"category"`, `"subcategory"` или `"folder"` — категория пакета вычисляется движком автоматически по пути к папке пакета относительно корня репозитория.
2. **Валидный формат JSON:**
   - Файл `manifest.json` должен быть синтаксически корректным JSON (UTF-8, без комментариев `//` или `/* */`, без висячих запятых).
3. **Кроссплатформенность (Linux `systemd` + macOS `launchd`):**
   - Для фоновых сервисов всегда создавайте стандартные юниты `systemd` (`.service` и при необходимости `.timer`).
   - **НЕ нужно** вручную писать `.plist` файлы для macOS: Deploy Engine на лету конвертирует `.service`, `.timer` и статические переменные из `.env` в XML `.plist` для `launchd` (`/Library/LaunchDaemons/com.deploy-engine.<pkg>.<unit>.plist`).
   - В хуках `post_install` / `pre_uninstall` используйте стандартные команды `systemctl` (`systemctl daemon-reload`, `systemctl enable --now <service>`) — движок сам адаптирует их под `launchctl` на macOS и безопасно сэмулирует в режиме `--sandbox`.

---

## 2. Формальная схема ключей `manifest.json` (Single-Package Mode)

```json
{
  "name": "string (optional, default: имя директории пакета, kebab-case/snake_case)",
  "version": "string (optional, default: \"1.0.0\", SemVer)",
  "desc": "string (optional, alias: \"description\" — краткое описание пакета на русском языке)",
  "active": true,
  "platforms": ["linux", "macos"],
  "requires": ["other-package-name"],
  "sys_packages": {
    "common": ["curl", "jq"],
    "apt": ["iproute2"],
    "brew": ["iproute2mac"],
    "apk": ["iproute2"],
    "dnf": ["iproute"],
    "pacman": ["iproute2"]
  },
  "python_packages": ["requests>=2.31.0"],
  "node_packages": [],
  "units": {
    "<unit_key>": {
      "type": "script | env | unit | service | timer | file | data | symlink",
      "src": "string (optional — относительный путь внутри папки пакета)",
      "dest": "string (optional, alias: \"target\" — абсолютный путь в ОС или путь с макросами)",
      "mode": "string (optional, alias: \"chmod\", например \"0755\", \"0644\", \"0600\")",
      "symlink": "string (required ТОЛЬКО если type == \"symlink\" — куда указывает ссылка)",
      "desc": "string (optional — краткое описание конкретного юнита для TUI и CLI info)"
    }
  },
  "pre_install": ["string command"],
  "post_install": ["string command"],
  "pre_uninstall": ["string command"],
  "post_uninstall": ["string command"]
}
```

---

## 3. Правила выбора `type` и путей в секции `units`

Каждый элемент в объекте `"units"` имеет ключ `<unit_key>` (обычно имя целевого файла, например `"my-script.sh"`, `".env"`, `"my-app.service"`, или `"files"` для папки приложения).

### Таблица допустимых значений `type`:

1. **`"script"`** (или автоопределение по расширению `.sh`, `.py`):
   - **Назначение:** исполняемые скрипты CLI и фоновых задач.
   - **Где хранить в пакете (`src`):** `scripts/<name>.sh` или `<name>.sh`.
   - **Дефолтный `dest` (если не указан):** `/usr/local/bin/<unit_key>` (Linux) / `/opt/homebrew/bin/<unit_key>` (macOS).
   - **Дефолтный `mode`:** `"0755"`.

2. **`"env"`** (или автоопределение по имени `.env`, `deploy.env` или расширению `.env`):
   - **Назначение:** конфигурационный файл переменных окружения и секретов.
   - **Где хранить в пакете (`src`):** `.env` или `deploy.env` в корне пакета.
   - **Дефолтный `dest` (если не указан):** `/etc/default/de_<pkg_name>/<pkg_name>.env`.
   - **Дефолтный `mode`:** `"0600"`.
   - **Правило шаблонизации `.env`:**
     Для запрашиваемых у пользователя параметров используйте синтаксис:
     - С дефолтным значением: `VAR_NAME="{{PROMPT:Описание параметра на русском:значение_по_умолчанию}}"`
     - Обязательный ввод без дефолта: `SECRET_KEY="{{PROMPT:Введите секретный ключ}}"`
     - Константа: `STATIC_VAR="value"`

3. **`"unit"`** (синоним **`"service"`**, или автоопределение по расширению `.service`):
   - **Назначение:** фоновый сервис `systemd` (на macOS автоматически конвертируется в `launchd` `.plist`).
   - **Где хранить в пакете (`src`):** `systemd/<name>.service` или `<name>.service`.
   - **Дефолтный `dest` (если не указан):** `/etc/systemd/system/<unit_key>`.
   - **Дефолтный `mode`:** `"0644"`.
   - **Рекомендация для `.service` файла:** подключайте файл окружения через `EnvironmentFile=-/etc/default/de_<pkg_name>/<pkg_name>.env` и вызывайте скрипты из `/usr/local/bin/<script>`.

4. **`"timer"`** (или автоопределение по расширению `.timer`):
   - **Назначение:** периодический таймер `systemd` (на macOS автоматически встраивается в `.plist` одноименного `.service`).
   - **Где хранить в пакете (`src`):** `systemd/<name>.timer` или `<name>.timer`.
   - **Дефолтный `dest` (если не указан):** `/etc/systemd/system/<unit_key>`.
   - **Дефолтный `mode`:** `"0644"`.
   - **Важно:** Имя основы `.timer` должно совпадать с именем основы `.service` (например, `sync-job.service` и `sync-job.timer`), чтобы на macOS транслятор объединил их в один `LaunchDaemon`.

5. **`"file"`** (по умолчанию для всех остальных расширений и папки `"files"`):
   - **Назначение:** конфигурационные файлы, статика, шаблоны или вся директория `files/`.
   - **Где хранить в пакете (`src`):** `files/<name>` или `<name>`. Если ключ юнита равен `"files"`, рекурсивно копируется содержимое папки `files/`.
   - **Дефолтный `dest` (если не указан):** `/opt/de_<pkg_name>/<unit_key>` (или `/opt/de_<pkg_name>` для ключа `"files"`).
   - **Дефолтный `mode`:** `"0644"` для файлов, `"0755"` для директорий.

6. **`"data"`**:
   - **Назначение:** изменяемые в процессе работы файлы данных (SQLite БД, JSON-состояния, счетчики), которые **нельзя затирать** при обновлении пакета и **нельзя удалять** при обычном `uninstall` (удаляются только с `--purge`).
   - **Дефолтный `dest` (если не указан):** `/var/lib/de_<pkg_name>/<unit_key>`.
   - **Дефолтный `mode`:** `"0600"`.

7. **`"symlink"`**:
   - **Назначение:** создание символической ссылки.
   - **Обязательное поле:** `"symlink": "/путь/на/который/ссылаемся"`.
   - **Поле `dest`:** где создать саму ссылку (по умолчанию `/usr/local/bin/<unit_key>` на Linux и `/opt/homebrew/bin/<unit_key>` на macOS).

---

## 4. Макросы подстановки в `manifest.json`

При указании кастомного поля `"dest"` в `units` или при написании команд в `pre_install`, `post_install`, `pre_uninstall`, `post_uninstall` используйте встроенные макросы вместо жестко закодированных путей, если требуется совместимость с macOS и песочницей:

- `{{PKG_NAME}}` — имя текущего пакета (`name`)
- `{{SYS_BIN}}` — `/usr/local/bin` (Linux) или `/opt/homebrew/bin` (macOS)
- `{{SYS_SYSTEMD}}` — `/etc/systemd/system` (Linux) или `/Library/LaunchDaemons` (macOS)
- `{{BASE_DIR}}` — `/opt/de_<name>`
- `{{ENV_DIR}}` — `/etc/default/de_<name>`
- `{{ENV_FILE}}` — `/etc/default/de_<name>/<name>.env`
- `{{DATA_DIR}}` — `/var/lib/de_<name>`
- `{{ROOT_DIR}}` — `/` (или корень песочницы)

---

## 5. Правила указания `platforms` и `sys_packages`

### 5.1. Допустимые идентификаторы в `platforms`
Используйте только нижний регистр:
- Семейства ОС: `"linux"`, `"macos"` (или `"darwin"`).
- Дистрибутивы Linux: `"debian"`, `"ubuntu"`, `"alpine"`, `"arch"`, `"fedora"`, `"rhel"`, `"centos"`.
- Если пакет работает везде, оставляйте `"platforms": ["linux", "macos"]` или `[]`.

### 5.2. Словарь `sys_packages`
Если имена системных пакетов различаются между `apt` и `brew` (например, `iproute2` в Linux vs `iproute2mac` в macOS, или `cron` только в Linux), всегда используйте объектный формат `sys_packages`:
```json
"sys_packages": {
  "common": ["curl", "jq"],
  "apt": ["iproute2", "dnsutils"],
  "brew": ["iproute2mac", "bind"],
  "apk": ["iproute2", "bind-tools"],
  "dnf": ["iproute", "bind-utils"],
  "pacman": ["iproute2", "bind"]
}
```

---

## 6. Мульти-пакетный формат `manifest.json`

Используйте мульти-пакетный формат, только если пользователь явно просит объединить несколько подпакетов в одной папке:
```json
{
  "units": {
    "shared-script.sh": {
      "type": "script",
      "src": "scripts/shared-script.sh",
      "desc": "Общий скрипт"
    }
  },
  "packages": {
    "pkg-alpha": {
      "version": "1.0.0",
      "desc": "Базовый модуль",
      "platforms": ["linux", "macos"],
      "include": ["shared-script.sh"],
      "units": {
        "alpha.sh": {
          "type": "script",
          "src": "scripts/alpha.sh",
          "desc": "Скрипт модуля Alpha"
        }
      }
    },
    "pkg-beta": {
      "version": "1.0.0",
      "desc": "Дополнительный модуль",
      "requires": ["pkg-alpha"],
      "include": ["shared-script.sh"]
    }
  }
}
```

---

## 7. Чек-лист самопроверки для LLM перед выдачей ответа

Перед тем как сгенерировать `manifest.json`, проверьте:
1. [ ] Все ли файлы, упомянутые в `units` (`src` или ключ юнита), реально существуют или сгенерированы в соответствующих папках (`scripts/`, `systemd/`, `files/`, корень пакета)?
2. [ ] У каждого ли юнита в `units` заполнено понятное поле `"desc"` и корректный `"type"`?
3. [ ] Если есть `.timer`, совпадает ли его префикс с `.service` (например, `app.timer` + `app.service`)?
4. [ ] Если есть `.env`, использует ли он `"type": "env"` и синтаксис `{{PROMPT:Описание:дефолт}}` для настраиваемых параметров?
5. [ ] Отсутствуют ли в `manifest.json` ключи, предназначенные для `category.json` (`order`, `title`)?
6. [ ] Добавлены ли в `post_install` и `pre_uninstall` команды управления сервисом/таймером (`systemctl daemon-reload`, `systemctl enable --now ...`)?

