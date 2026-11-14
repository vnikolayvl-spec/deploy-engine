"""
Non-destructive ENV upsert manager supporting local presets in ./env/ without modifying package repos.
"""
import os
import re
import shutil
import sys
from typing import Dict, Optional
from lib.config import ENV_PATH, ENV_PREFIX, LOCAL_ENV_DIR
from lib.core.execution_context import ExecutionContext
from lib.env.env_parser import EnvParser
from lib.env.secret_masker import SecretMasker
from lib.installer.transaction_manager import TransactionManager


class EnvUpsertManager:
    """
    Неразрушающее обновление переменных окружения (ENV upsert).
    Поддерживает чтение и сохранение пользовательских предустановок в папке ./env/,
    чтобы не изменять исходные файлы в репозитории пакетов и не задавать повторно вопросы.
    """

    def __init__(
        self,
        context: Optional[ExecutionContext] = None,
        transaction_manager: Optional[TransactionManager] = None,
        provider=None,
        local_env_dir: Optional[str] = None,
    ):
        self.context = context or ExecutionContext()
        self.transaction_manager = transaction_manager or TransactionManager()
        self.provider = provider
        self.local_env_dir = local_env_dir or LOCAL_ENV_DIR
        self.parser = EnvParser()
        self.masker = SecretMasker()

    def get_env_dir(self, pkg_name: str) -> str:
        """Возвращает системный каталог окружения пакета с учетом провайдера ОС."""
        env_base = self.provider.get_paths()["env_path"] if self.provider else ENV_PATH
        return os.path.join(env_base, f"{ENV_PREFIX}{pkg_name}")

    def get_local_preset_path(self, pkg_name: str) -> str:
        """Возвращает путь к локальному файлу предустановок ./env/<pkg_name>.env."""
        return os.path.abspath(os.path.join(self.local_env_dir, f"{pkg_name}.env"))

    def save_local_preset(self, pkg_name: str, template_path: str, values: Dict[str, str]) -> str:
        """
        Сохраняет отредактированные в TUI переменные в ./env/<pkg_name>.env,
        не затрагивая исходный файл шаблона в репозитории пакетов.
        """
        preset_path = self.get_local_preset_path(pkg_name)
        os.makedirs(os.path.dirname(preset_path), exist_ok=True)
        rendered = self.parser.render_with_values(template_path, values)
        with open(preset_path, "w", encoding="utf-8") as f:
            f.write(rendered)
        os.chmod(preset_path, 0o600)
        return preset_path

    @staticmethod
    def _infer_pkg_name_from_dest(dest_path: str) -> Optional[str]:
        """Определяет имя пакета из целевого пути вида .../de_<pkg>/<pkg>.env."""
        parent = os.path.basename(os.path.dirname(dest_path))
        if parent.startswith(ENV_PREFIX):
            return parent[len(ENV_PREFIX) :]
        fname = os.path.basename(dest_path)
        if fname.endswith(".env") and fname != "deploy.env":
            return fname[:-4]
        return None

    def upsert_env_file(self, src_path: str, dest_path: str, pkg_name: Optional[str] = None) -> bool:
        """
        Обновляет целевой .env:
        - Если в ./env/<pkg>.env есть сохраненная предустановка, берет значения из нее без опроса пользователя.
        - Если целевой файл существует и clean_env=False, дописывает только новые переменные.
        """
        dest_dir = os.path.dirname(dest_path)
        inferred_pkg = pkg_name or self._infer_pkg_name_from_dest(dest_path)
        preset_path = self.get_local_preset_path(inferred_pkg) if inferred_pkg else None
        effective_src = preset_path if (preset_path and os.path.isfile(preset_path)) else src_path

        src_keys, src_lines = self.parser.parse_file(effective_src)

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

        if not os.path.exists(dest_path) or self.context.clean_env:
            with open(effective_src, "r", encoding="utf-8") as f:
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
        """Удаляет системный каталог ENV пакета только при purge=True с проверкой pkg_name на пустоту."""
        clean_pkg = (pkg_name or "").strip()
        if not clean_pkg or "/" in clean_pkg or clean_pkg in (".", "..") or "*" in clean_pkg:
            self.context.log("🛑 Пропуск удаления ENV: пустое или некорректное имя пакета.")
            return

        env_dir = os.path.normpath(self.get_env_dir(clean_pkg))
        expected_tail = f"{ENV_PREFIX}{clean_pkg}"
        if os.path.basename(env_dir) != expected_tail or len([s for s in env_dir.strip("/").split("/") if s]) < 2:
            self.context.log(f"🛑 Заблокировано удаление некорректного каталога ENV: {env_dir}")
            return

        if not os.path.exists(env_dir):
            return

        if purge:
            if self.context.dry_run:
                self.context.log(f"🔎 [DRY-RUN][PURGE] Удаление каталога окружения и секретов: {env_dir}")
                return
            self.context.log(f"🔥 [PURGE] Удаление каталога окружения и секретов: {env_dir}")
            shutil.rmtree(env_dir, ignore_errors=True)
        else:
            self.context.log(f"🔒 Каталог окружения сохранен: {env_dir} (для удаления используйте --purge)")

    def _resolve_prompts(self, text: str) -> str:
        """
        Разрешает оставшиеся макросы {{PROMPT:...}}.
        Если все промпты уже заполнены через предустановку в ./env/, вопросы не задаются.
        """
        pattern = re.compile(r"\{\{PROMPT:(.*?)\}\}")
        if not pattern.search(text):
            return text

        is_interactive = sys.stdin.isatty() and not os.environ.get("DE_NONINTERACTIVE") and not self.context.non_interactive

        def replace_match(match: re.Match) -> str:
            inner = match.group(1).strip()
            default_val = ""
            notice = inner

            if ":" in inner and not inner.endswith(")"):
                left, right = inner.rsplit(":", 1)
                if "(" not in right and ")" not in right:
                    notice = left.strip()
                    default_val = right.strip()

            if is_interactive:
                print(f"\n💬 [ПОДКАЗКА]: {notice}")
                prompt_msg = (
                    f"👉 Введите значение [{default_val}]: "
                    if default_val
                    else "👉 Введите значение (Enter для значения по умолчанию): "
                )
                try:
                    sys.stdout.write(prompt_msg)
                    sys.stdout.flush()
                    with open("/dev/tty", "r", encoding="utf-8") as tty:
                        line = tty.readline()
                        if line == "":
                            raise KeyboardInterrupt()
                        user_input = line.strip()
                    return user_input if user_input else default_val
                except KeyboardInterrupt:
                    raise
                except Exception:
                    return default_val

            return default_val

        return pattern.sub(replace_match, text)
