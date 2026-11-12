"""
Parser for environment (.env) files preserving comments, structure, and {{PROMPT:...}} metadata.
"""
import os
import re
from typing import Any, Dict, List, Optional, Tuple


class EnvParser:
    """Парсер .env файлов с сохранением структуры строк, комментариев и разбором {{PROMPT:...}}."""

    PROMPT_RE = re.compile(r"\{\{PROMPT:(.*?)\}\}")

    @classmethod
    def extract_prompt_info(cls, raw_val: str) -> Tuple[bool, str, str]:
        """
        Извлекает информацию из макроса {{PROMPT:описание:дефолт}}.
        Возвращает (has_prompt, notice, resolved_default_value).
        """
        match = cls.PROMPT_RE.search(raw_val)
        if not match:
            return False, "", raw_val

        notices: List[str] = []

        def _replace(m: re.Match) -> str:
            inner = m.group(1).strip()
            default_val = ""
            notice = inner
            if ":" in inner and not inner.endswith(")"):
                left, right = inner.rsplit(":", 1)
                if "(" not in right and ")" not in right:
                    notice = left.strip()
                    default_val = right.strip()
            notices.append(notice)
            return default_val

        resolved_val = cls.PROMPT_RE.sub(_replace, raw_val)
        return True, "; ".join(notices), resolved_val

    def parse_lines(self, content: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """
        Парсит текст .env.
        Возвращает кортеж: (словарь {ключ: значение}, список распарсенных строк с метаданными).
        """
        key_values: Dict[str, str] = {}
        parsed_lines: List[Dict[str, Any]] = []

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                parsed_lines.append({"type": "blank", "raw": line})
                continue
            if stripped.startswith("#"):
                parsed_lines.append({"type": "comment", "raw": line})
                continue

            if "=" in line:
                key, val = line.split("=", 1)
                k = key.strip()
                v = val.strip()
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    unquoted_val = v[1:-1]
                else:
                    unquoted_val = v

                key_values[k] = unquoted_val
                parsed_lines.append({"type": "pair", "key": k, "value": unquoted_val, "raw": line})
            else:
                parsed_lines.append({"type": "other", "raw": line})

        return key_values, parsed_lines

    def parse_file(self, file_path: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """Считывает и парсит файл .env."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return self.parse_lines(content)
        except Exception:
            return {}, []

    def parse_editable_entries(
        self,
        template_path: str,
        override_paths: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Формирует список всех переменных из шаблона .env для редактирования в TUI,
        накладывая сохраненные значения из локальной папки env/ или установленного файла.
        """
        _, lines = self.parse_file(template_path)
        overrides: Dict[str, str] = {}
        for path in override_paths or []:
            if path and os.path.isfile(path):
                kv, _ = self.parse_file(path)
                for k, v in kv.items():
                    has_p, _, _ = self.extract_prompt_info(v)
                    if not has_p:
                        overrides[k] = v

        entries: List[Dict[str, Any]] = []
        pending_comments: List[str] = []

        for item in lines:
            if item["type"] == "comment":
                clean_c = item["raw"].lstrip("#").strip()
                if clean_c and not clean_c.startswith("===") and not clean_c.startswith("---"):
                    pending_comments.append(clean_c)
            elif item["type"] == "blank":
                pending_comments.clear()
            elif item["type"] == "pair":
                k = item["key"]
                raw_val = item["value"]
                has_prompt, notice, default_val = self.extract_prompt_info(raw_val)
                comment_str = " ".join(pending_comments)
                pending_comments.clear()

                current_val = overrides.get(k, default_val if has_prompt else raw_val)
                entries.append(
                    {
                        "key": k,
                        "value": current_val,
                        "default_value": default_val,
                        "has_prompt": has_prompt,
                        "notice": notice or comment_str,
                        "comment": comment_str,
                    }
                )
        return entries

    def render_with_values(self, template_path: str, values: Dict[str, str]) -> str:
        """
        Генерирует текст .env на базе структуры и комментариев шаблона,
        подставляя отредактированные пользователем значения без макросов {{PROMPT:...}}.
        """
        _, lines = self.parse_file(template_path)
        out_lines: List[str] = []
        seen_keys = set()

        for item in lines:
            if item["type"] == "pair":
                k = item["key"]
                seen_keys.add(k)
                if k in values:
                    val = values[k]
                    raw_line = item["raw"]
                    eq_rhs = raw_line.split("=", 1)[1].strip() if "=" in raw_line else ""
                    if (eq_rhs.startswith('"') and eq_rhs.endswith('"')) or (" " in val and not val.startswith('"')):
                        out_lines.append(f'{k}="{val}"')
                    else:
                        out_lines.append(f"{k}={val}")
                else:
                    _, _, def_val = self.extract_prompt_info(item["value"])
                    out_lines.append(f"{k}={def_val}")
            else:
                out_lines.append(item["raw"])

        for k, val in values.items():
            if k not in seen_keys:
                out_lines.append(f"{k}={val}")

        return "\n".join(out_lines) + "\n"
