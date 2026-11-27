"""
Non-destructive ENV upsert manager supporting local presets in ./env/, comments, #GEN:...#, and safe #SKIP#.
"""
import os
import re
import shutil
import sys
from typing import Dict, List, Optional, Tuple
from lib.config import ENV_PATH, ENV_PREFIX, LOCAL_ENV_DIR
from lib.core.execution_context import ExecutionContext
from lib.env.env_generator import EnvGenerator
from lib.env.env_parser import EnvParser
from lib.env.secret_masker import SecretMasker
from lib.installer.transaction_manager import TransactionManager


class EnvUpsertManager:
    """
    Неразрушающее обновление переменных окружения (ENV upsert) с сохранением комментариев,
    автоматической генерацией #GEN:...# и безопасным раскрытием #SKIP#.
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

    def has_saved_preset(self, pkg_name: str) -> bool:
        """Возвращает True, если во внутреннем хранилище есть сохраненный пресет пакета."""
        try:
            return os.path.isfile(self.get_local_preset_path(pkg_name))
        except OSError:
            return False

    def needs_env_confirmation(self, pkg_name: str, template_path: str) -> bool:
        """Возвращает True, если перед установкой требуется обязательное подтверждение .env."""
        if self.context.clean_env or not self.has_saved_preset(pkg_name):
            return True
        preset_path = self.get_local_preset_path(pkg_name)
        entries = self.parser.parse_editable_entries(template_path, override_paths=[preset_path])
        for entry in entries:
            val = str(entry.get("value", "")).strip()
            if entry.get("required_prompt") and not val and not EnvGenerator.is_skip_value(val):
                return True
        return False

    @staticmethod
    def _atomic_write_0600(path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)

    def save_local_preset(self, pkg_name: str, template_path: str, values: Dict[str, str]) -> str:
        """
        Сохраняет отредактированные переменные в <LOCAL_ENV_DIR>/<pkg>.env,
        сохраняя комментарии и разворачивая стандартные #GEN:...# (оставляя #SKIP# и #GEN:pkg:...#).
        """
        preset_path = self.get_local_preset_path(pkg_name)
        existing = preset_path if os.path.isfile(preset_path) else None
        rendered = self.parser.render_with_values(template_path, values, existing_path=existing)
        materialized, _ = EnvGenerator.materialize_env_text(rendered, for_system=False)
        self._atomic_write_0600(preset_path, materialized)
        return preset_path

    def apply_preset_to_system_env(
        self, pkg_name: str, template_path: str, dest_path: str, values: Dict[str, str]
    ) -> Tuple[str, Optional[str]]:
        """Сохраняет пресет во внутреннее хранилище и применяет его в системный .env с бэкапом .de_bak."""
        preset_path = self.save_local_preset(pkg_name, template_path, values)
        try:
            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, mode=0o700, exist_ok=True)
            if os.path.isfile(dest_path):
                shutil.copy2(dest_path, f"{dest_path}.de_bak")
            with open(preset_path, "r", encoding="utf-8") as src_f:
                preset_content = src_f.read()
            sys_content, _ = EnvGenerator.materialize_env_text(preset_content, for_system=True)
            self._atomic_write_0600(dest_path, sys_content)
            return preset_path, None
        except PermissionError:
            warn = (
                f"❗ Пресет сохранен ({preset_path}), но нет прав на запись системного файла '{dest_path}'. "
                f"Запустите с sudo или выполните: sudo deploy-engine config {pkg_name}"
            )
            return preset_path, warn
        except OSError as err:
            return preset_path, f"❗ Пресет сохранен ({preset_path}), но не удалось обновить '{dest_path}': {err}"

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
        Обновляет целевой .env неразрушающим образом:
        - переносит комментарии над новыми ключами;
        - разворачивает #GEN:...# (кроме #GEN:pkg:...#);
        - безопасно раскрывает #SKIP# в пустое значение с меткой '# #SKIP#' в системном .env.
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

        approval_cb = getattr(self.context, "env_approval_callback", None)
        approved_from_tui: Optional[Dict[str, str]] = None
        if callable(approval_cb) and inferred_pkg:
            approved_from_tui = approval_cb(inferred_pkg, src_path, dest_path)
            if isinstance(approved_from_tui, dict):
                preset_path = self.save_local_preset(inferred_pkg, src_path, approved_from_tui)
                effective_src = preset_path
                src_keys, src_lines = self.parser.parse_file(effective_src)

        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, mode=0o700, exist_ok=True)
            self.transaction_manager.record_created_dir(dest_dir)

        if not os.path.exists(dest_path) or self.context.clean_env or isinstance(approved_from_tui, dict):
            with open(effective_src, "r", encoding="utf-8") as f:
                content = f.read()

            content, prompted = self._resolve_prompts_with_flag(content)
            preset_content, gen_keys = EnvGenerator.materialize_env_text(content, for_system=False)
            if (prompted or gen_keys) and inferred_pkg and preset_path:
                self._atomic_write_0600(preset_path, preset_content)

            sys_content, _ = EnvGenerator.materialize_env_text(preset_content, for_system=True)

            if os.path.exists(dest_path):
                backup_path = f"{dest_path}.de_bak"
                shutil.copy2(dest_path, backup_path)
                self.transaction_manager.record_backup(dest_path, backup_path)
            else:
                self.transaction_manager.record_created_file(dest_path)

            self._atomic_write_0600(dest_path, sys_content)
            gen_note = f" (сгенерированы ключи: {', '.join(gen_keys)})" if gen_keys else ""
            self.context.log(f"🔐 Сконфигурирован ENV файл: {dest_path}{gen_note}")
            return True

        existing_keys, _ = self.parser.parse_file(dest_path)
        new_blocks: List[str] = []
        added_count = 0

        for item in src_lines:
            if item["type"] == "pair":
                k = item["key"]
                if k not in existing_keys:
                    resolved_raw = self._resolve_prompts(item["raw"])
                    mat_line, _ = EnvGenerator.materialize_env_text(resolved_raw, for_system=True)
                    leading = item.get("leading_comments") or []
                    if leading:
                        new_blocks.extend(leading)
                    new_blocks.append(mat_line.rstrip("\n"))
                    added_count += 1

        if added_count > 0:
            backup_path = f"{dest_path}.de_bak"
            shutil.copy2(dest_path, backup_path)
            self.transaction_manager.record_backup(dest_path, backup_path)

            with open(dest_path, "a", encoding="utf-8") as f:
                f.write("\n\n# --- Added by Deploy Engine update ---\n")
                for line in new_blocks:
                    f.write(f"{line}\n")
            os.chmod(dest_path, 0o600)
            self.context.log(f"🔄 В ENV {dest_path} добавлены новые переменные ({added_count} шт.)")
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

    def _resolve_prompts_with_flag(self, text: str) -> tuple[str, bool]:
        """Разрешает макросы {{PROMPT:...}}, опрашивая через /dev/tty только поля без дефолта."""
        pattern = re.compile(r"\{\{PROMPT:(.*?)\}\}")
        if not pattern.search(text):
            return text, False

        is_interactive = (
            sys.stdin.isatty()
            and not os.environ.get("DE_NONINTERACTIVE")
            and not self.context.non_interactive
            and not getattr(self.context, "in_tui", False)
        )
        was_prompted = False

        def replace_match(match: re.Match) -> str:
            nonlocal was_prompted
            inner = match.group(1).strip()
            default_val = ""
            notice = inner

            if ":" in inner and not inner.endswith(")"):
                left, right = inner.rsplit(":", 1)
                if "(" not in right and ")" not in right:
                    notice = left.strip()
                    default_val = right.strip()
                    if default_val.startswith("default="):
                        default_val = default_val[len("default=") :].strip()

            if is_interactive and default_val == "":
                print(f"\n💬 [ОБЯЗАТЕЛЬНЫЙ ПАРАМЕТР]: {notice}")
                try:
                    sys.stdout.write("👉 Введите значение (или #SKIP# для пропуска): ")
                    sys.stdout.flush()
                    with open("/dev/tty", "r", encoding="utf-8") as tty:
                        line = tty.readline()
                        if line == "":
                            raise KeyboardInterrupt()
                        user_input = line.strip()
                    was_prompted = True
                    return user_input
                except KeyboardInterrupt:
                    raise
                except Exception:
                    return default_val

            return default_val

        return pattern.sub(replace_match, text), was_prompted

    def _resolve_prompts(self, text: str) -> str:
        resolved, _ = self._resolve_prompts_with_flag(text)
        return resolved
