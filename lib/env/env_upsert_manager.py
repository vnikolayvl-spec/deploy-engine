"""
Non-destructive ENV upsert manager.
"""
import os
import re
import shutil
import sys
from typing import Optional
from deploy_config import ENV_PATH, ENV_PREFIX
from lib.core.execution_context import ExecutionContext
from lib.env.env_parser import EnvParser
from lib.env.secret_masker import SecretMasker
from lib.installer.transaction_manager import TransactionManager


class EnvUpsertManager:
    """Неразрушающее обновление переменных окружения (ENV upsert)."""

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        transaction_manager: Optional[TransactionManager] = None,
    ):
        self.context = context or ExecutionContext()
        self.transaction_manager = transaction_manager or TransactionManager()
        self.parser = EnvParser()
        self.masker = SecretMasker()

    def get_env_dir(self, pkg_name: str) -> str:
        """Возвращает каталог окружения пакета (/etc/default/de_{pkg})."""
        return os.path.join(ENV_PATH, f"{ENV_PREFIX}{pkg_name}")

    def upsert_env_file(self, src_path: str, dest_path: str) -> bool:
        """
        Обновляет целевой .env:
        - Если файл не существует, создается из шаблона.
        - Если существует и context.clean_env=True, сбрасывается к заводским настройкам.
        - Если существует и context.clean_env=False, дописываются только НОВЫЕ переменные.
          Существующие пользовательские значения и секреты не изменяются.
        """
        dest_dir = os.path.dirname(dest_path)

        # Читаем шаблон
        src_keys, src_lines = self.parser.parse_file(src_path)

        if self.context.dry_run:
            if not os.path.exists(dest_path) or self.context.clean_env:
                self.context.log(f"🔎 [DRY-RUN] ENV: Создание/перезапись {dest_path}")
            else:
                existing_keys, _ = self.parser.parse_file(dest_path)
                new_keys = [k for k in src_keys if k not in existing_keys]
                if new_keys:
                    self.context.log(f"🔎 [DRY-RUN] ENV: Будут добавлены новые ключи в {dest_path}: {', '.join(new_keys)}")
                else:
                    self.context.log(f"🔎 [DRY-RUN] ENV: Все ключи уже присутствуют в {dest_path}, изменений нет.")
            return True

        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, mode=0o700, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)

        # Случай 1: Файл не существует или запрошена чистая установка (--clean-env)
        if not os.path.exists(dest_path) or self.context.clean_env:
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()

            content = self._resolve_prompts(content)

            if os.path.exists(dest_path):
                backup_path = f"{dest_path}.de_bak"
                shutil.copy2(dest_path, backup_path)
                self.transaction_manager.record_backup(dest_path, backup_path)
            else:
                self.transaction_manager.record_created_file(dest_path)

            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.chmod(dest_path, 0o600)
            self.context.log(f"🔐 Сконфигурирован ENV файл: {dest_path}")
            return True

        # Случай 2: Неразрушающий upsert в существующий файл
        existing_keys, _ = self.parser.parse_file(dest_path)
        new_lines_to_append = []

        for item in src_lines:
            if item["type"] == "pair":
                k = item["key"]
                if k not in existing_keys:
                    resolved_raw = self._resolve_prompts(item["raw"])
                    new_lines_to_append.append(resolved_raw)

        if new_lines_to_append:
            backup_path = f"{dest_path}.de_bak"
            shutil.copy2(dest_path, backup_path)
            self.transaction_manager.record_backup(dest_path, backup_path)

            with open(dest_path, "a", encoding="utf-8") as f:
                f.write("\n\n# --- Added by Deploy Engine update ---\n")
                for line in new_lines_to_append:
                    f.write(f"{line}\n")
            os.chmod(dest_path, 0o600)
            self.context.log(f"🔄 В ENV {dest_path} добавлены новые переменные ({len(new_lines_to_append)} шт.)")
        else:
            self.context.log(f"🔒 ENV {dest_path} актуален, существующие секреты не затронуты.")

        return True

    def remove_env(self, pkg_name: str, purge: bool = False) -> None:
        """
        Удаляет каталог ENV пакета только при purge=True.
        По умолчанию сохраняет каталог секретов.
        """
        env_dir = self.get_env_dir(pkg_name)
        if not os.path.exists(env_dir):
            return

        if purge:
            self.context.log(f"🔥 [PURGE] Удаление каталога окружения и секретов: {env_dir}")
            shutil.rmtree(env_dir, ignore_errors=True)
        else:
            self.context.log(f"🔒 Каталог окружения сохранен: {env_dir} (для удаления используйте --purge)")

    def _resolve_prompts(self, text: str) -> str:
        """
        Разрешает макросы подсказок вида {{PROMPT:notice}} и {{PROMPT:key:default}}.
        В интерактивном терминале запрашивает значение у пользователя.
        В неинтерактивном режиме подставляет значение по умолчанию или пустую строку.
        """
        pattern = re.compile(r"\{\{PROMPT:(.*?)\}\}")
        is_interactive = sys.stdin.isatty() and not os.environ.get("DE_NONINTERACTIVE")

        def replace_match(match: re.Match) -> str:
            inner = match.group(1).strip()
            default_val = ""
            notice = inner

            # Формат {{PROMPT:notice_or_key:default}} (если правая часть после ':' не закрывает скобку)
            if ":" in inner and not inner.endswith(")"):
                left, right = inner.rsplit(":", 1)
                if "(" not in right and ")" not in right:
                    notice = left.strip()
                    default_val = right.strip()

            if is_interactive:
                print(f"\n💬 [ПОДКАЗКА]: {notice}")
                prompt_msg = f"👉 Введите значение [{default_val}]: " if default_val else "👉 Введите значение (Enter для значения по умолчанию): "
                try:
                    sys.stdout.write(prompt_msg)
                    sys.stdout.flush()
                    with open("/dev/tty", "r", encoding="utf-8") as tty:
                        user_input = tty.readline().strip()
                    return user_input if user_input else default_val
                except Exception:
                    return default_val

            return default_val

        return pattern.sub(replace_match, text)
