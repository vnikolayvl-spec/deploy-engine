# 🤖 Deploy Engine (версия 9.0.0) — Техническая спецификация для LLM

Данный документ описывает архитектуру, модульную структуру, правила разработки, ключи CLI и переменные окружения `deploy-engine` для языковых моделей и разработчиков.

---

## 🏛️ Архитектурные ограничения и правила кода

1. **Строго 1 класс на файл**: каждый `.py` файл содержит не более одного класса (либо чистые функции-утилиты, если класса нет).
2. **Максимум 300 строк на файл**: ни один `.py` файл не должен превышать 300 строк кода.
3. **Полноширинные иконки в TUI (`East_Asian_Width = W`)**: запрещено использовать составные эмодзи с `\ufe0f` и узкой шириной `N` (`⚠️`, `⚙️`, `♻️`, `🗑️`, `🛡️`, `⏱️`, `ℹ️`). Используются только полноширинные символы (`❗`, `🔧`, `🔄`, `🧹`, `🔒`, `⏰`, `💡`, `✅`, `❌`, `📦`, `📋`, `🚀`, `⏳`).
4. **Универсальные русские хоткеи**: все горячие клавиши в TUI и модальных окнах поддерживают маппинг `ЙЦУКЕН <-> QWERTY` (`q-q` / `й-й`, `e` / `у`).
5. **Безопасность и идемпотентность**:
   - Запрещено вызывать `rm` в хуках манифеста (`pre_install`, `post_install`, `pre_uninstall`, `post_uninstall`).
   - Любая транзакция установки поддерживает атомарный LIFO-откат (`TransactionManager`) при ошибке или `Ctrl+C`.
   - Юниты `data` (`/var/lib/de_<pkg>`) никогда не перезаписываются при переустановке.
   - Юниты `env` (`/etc/default/de_<pkg>/<pkg>.env`) обновляются неразрушающим образом (`EnvUpsertManager`), сброс — только по `--clean-env`.

---

## 📁 Структура директорий и модулей

```text
deploy-engine/
├── manifest.json              # Манифест для самоустановки движка в /opt/de_deploy-engine
├── deploy.env                 # Шаблон системной конфигурации (/etc/default/de_deploy-engine/deploy-engine.env)
├── VERSION.txt                # Номер версии (9)
├── COMMIT.txt                 # Описание текущего релиза
├── CHANGELOG.txt              # История изменений по версиям
├── README.md                  # Пользовательская документация с описанием всех ключей и ENV
├── LLM.md                     # Архитектурная спецификация для ИИ (этот файл)
├── scripts/
│   ├── deploy-engine.sh       # Системный CLI лаунчер -> {{SYS_BIN}}/deploy-engine
│   └── deploy-ui.sh           # Системный TUI лаунчер -> {{SYS_BIN}}/deploy-ui
├── tests/                     # Модульные и интеграционные тесты (unittest)
└── files/
    ├── main.py                # Единая точка входа (CLI + TUI, <= 300 строк)
    ├── app.env.example        # Пример локального файла конфигурации
    └── lib/
        ├── config.py          # Иерархический загрузчик конфигурации и путей
        ├── engine.py          # Реэкспорт фасада Engine
        ├── ui_app.py          # Главный 3-колоночный экран TUI (DeployApp)
        ├── utils.py           # Проверка прав root, авторазвертывание .venv для Textual и маппинг хоткеев
        ├── core/
        │   ├── engine.py                    # Главный фасад оркестратора (Engine)
        │   ├── execution_context.py         # Контекст выполнения, потоковый запуск процессов (run_logged_subprocess) и маршрутизация логов по пакетам
        │   ├── deploy_engine_error.py       # Базовое исключение DeployEngineError
        │   ├── manifest_validation_error.py # Ошибка валидации манифеста
        │   ├── name_collision_error.py      # Ошибка коллизии коротких имен пакетов
        │   ├── dependency_cycle_error.py    # Ошибка циклической зависимости
        │   └── rollback_error.py            # Ошибка отката транзакции
        ├── discovery/
        │   ├── directory_crawler.py         # Терминальный обходчик дерева пакетов (игнорирует _*)
        │   ├── category_manifest_parser.py  # Парсер category.json
        │   ├── manifest_parser.py           # Парсер и нормализатор manifest.json
        │   ├── name_collision_resolver.py   # Разрешение имен, пространств имен и алиасов по имени папки
        │   ├── package_cache_manager.py     # Кэширование реестра в packages.json с TTL 60 минут
        │   └── package_registry.py          # Центральный реестр пакетов и категорий
        ├── dependencies/
        │   ├── dependency_graph.py          # Топологическая сортировка зависимостей (алгоритм Кана)
        │   ├── system_pkg_manager.py        # Пакетная установка системных зависимостей через провайдер ОС
        │   ├── python_pkg_manager.py        # Установка pip / requirements.txt
        │   └── node_pkg_manager.py          # Установка npm зависимостей
        ├── providers/
        │   ├── base_provider.py             # Абстрактный провайдер окружения ОС
        │   ├── linux_provider.py            # Провайдер Linux (systemd + apt/dnf/yum/apk/pacman с кэш-TTL 60 мин)
        │   ├── macos_provider.py            # Провайдер macOS (launchd .plist + brew/port)
        │   ├── sandbox_provider.py          # Провайдер локальной песочницы (--sandbox)
        │   ├── provider_factory.py          # Фабрика провайдеров окружения
        │   └── systemd_to_plist_converter.py# Конвертер .service + .timer + .env -> launchd XML .plist
        ├── installer/
        │   ├── unit_path_resolver.py        # Расчет системных путей и прав доступа по типам юнитов
        │   ├── data_unit_installer.py       # Установка постоянных данных (/var/lib/de_<pkg>) без перезаписи
        │   ├── transaction_manager.py       # Журнал транзакций с атомарным LIFO-откатом
        │   └── file_installer.py            # Копирование файлов/директорий, симлинки, декларативные dirs/chmod
        ├── env/
        │   ├── env_parser.py                # Парсер .env с сохранением комментариев и разбором {{PROMPT:...}}
        │   ├── secret_masker.py             # Маскирование секретов в логах
        │   └── env_upsert_manager.py        # Неразрушающий upsert .env, пресеты ./env/<pkg>.env, callback подтверждения из TUI
        ├── lifecycle/
        │   ├── hook_context.py              # Интерполяция макросов ({{SYS_BIN}}, {{ENV_DIR}}, {{DATA_DIR}})
        │   └── hook_executor.py             # Выполнение хуков с блокировкой rm в манифестах
        ├── state/
        │   ├── state_repository.py          # Управление /etc/default/state.json (с сохранением manifest_path)
        │   ├── package_inspector.py         # Инспекция пакетов (list, info, статус служб, логи install_DATE.log)
        │   └── backup_manager.py            # Версионированные бэкапы и восстановление (backup / restore)
        ├── remote/
        │   ├── ssh_client.py                # Выполнение команд и передача файлов через ssh/scp
        │   └── remote_deployer.py           # Двухуровневый удаленный деплой (Полный и Сокращенный режимы, Remote TUI)
        └── ui/
            ├── package_tree.py              # Дерево пакетов, бэкапов и архивов восстановления
            ├── plan_preview.py              # Виджет предпросмотра плана развертывания
            ├── env_editor_modal.py          # Компактное модальное окно редактирования .env [E]
            ├── package_env_panel.py         # Встроенная панель редактирования и подтверждения .env на вкладке пакета
            ├── execution_modal.py           # Многовкладочное окно выполнения операций (Общий лог + вкладки пакетов)
            ├── package_details_modal.py     # Карточка пакета (инфо, лог установки, статус/логи службы)
            └── styles.py                    # Таблица стилей CSS для Textual
```

---

## 🔑 Ключи запуска (`main.py`) и переменные ENV

### Ключи командной строки
- **Позиционные аргументы (`pos_args`)**: команда (`install`, `uninstall`, `reinstall`, `backup`, `restore`, `list`, `info`, `scan`, `tui`, `help`) и/или имена целевых пакетов (или путь к папке/манифесту).
- **`--tui`, `-u`**: принудительный запуск TUI.
- **`--info`, `-i [ПАКЕТ]`**: вывод подробной карточки пакета в CLI.
- **`--manifest`, `-m <ПУТЬ>`**: путь к `manifest.json` или папке пакетов.
- **`--packages-dir`, `-d <ПУТЬ>`**: корневая директория дерева пакетов.
- **`--comment`, `-c <ТЕКСТ>`**: комментарий к бэкапу (`backup`).
- **`--backup`, `-b <СЕЛЕКТОР>`**: номер, штамп времени или имя архива для `restore`.
- **`--list`, `-l`**: вывод списка доступных бэкапов (`backup` / `restore`).
- **`--sandbox [ОС]`**: режим песочницы (`debian`, `ubuntu`, `alpine`, `arch`, `fedora`, `macos`).
- **`--sandbox-dir <ПУТЬ>`**: директория песочницы (по умолчанию `./.de_sandbox`).
- **`--dry-run`, `-n`**: холостой прогон без изменения диска.
- **`--purge`**: полное удаление каталогов `ENV` и `Data` при `uninstall`.
- **`--clean-env`**: перезапись существующего `.env` шаблоном при установке.
- **`--rescan`**: принудительное обновление `packages.json`.
- **`--remote`, `-r [user@]host[:port]`**: удаленное выполнение по SSH.
- **`--remote-dir <ПУТЬ>`**: каталог `deploy-engine` на удаленном сервере (по умолчанию `/opt/de_deploy-engine`).
- **`--config <ФАЙЛ>`**: путь к кастомному `.env` файлу движка.
- **`--yes`, `-y`**: неинтерактивный режим CLI без запросов `/dev/tty`.
- **`--json`**: вывод в формате JSON.
- **`--verbose`, `-v`**: подробный отладочный вывод.

### Переменные окружения (`ENV`)
- `DE_CONFIG_FILE` — путь к кастомному `.env` конфигурации движка.
- `DE_NONINTERACTIVE` — неинтерактивный режим (`1` / `true`).
- `DE_DATA_DIR` — каталог данных движка (`/var/lib/de_deploy-engine`).
- `DE_PACKAGES_DIR` — каталог пакетов (`/var/lib/de_deploy-engine/packages` или `./packages`).
- `DE_PACKAGES_CACHE` — файл кэша манифестов (`packages.json`).
- `DE_LOCAL_ENV_DIR` — каталог локальных пресетов (`./env` или `/var/lib/de_deploy-engine/env`).
- `DE_BACKUP_DIR` — каталог бэкапов (`./backup` или `/var/lib/de_deploy-engine/backup`).
- `DE_REMOTE_ENGINE_DIR` — путь к движку на удаленном хосте (`/opt/de_deploy-engine`).
- `DE_SYS_BIN` — путь к системным бинарникам (`/usr/local/bin`).
- `DE_SYS_SYSTEMD` — путь к юнитам systemd (`/etc/systemd/system`).
- `DE_ENV_PATH` — путь к каталогу окружения (`/etc/default`).
- `DE_STATE_DIR` — путь к каталогу состояния (`/var/lib`).
- `DE_VENV_PATH` — путь к виртуальному окружению Python (`.venv`).
