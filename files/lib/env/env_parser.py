"""
Parser for environment (.env) files preserving comments, inline comments, #AUTO#, #GEN:...#, #SKIP#, and {{PROMPT:...}}.
"""
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from lib.env.env_generator import EnvGenerator


class EnvParser:
    """Парсер .env файлов с сохранением комментариев, инлайн-комментариев, #AUTO#, #GEN# и #SKIP#."""

    PROMPT_RE = re.compile(r"\{\{PROMPT:(.*?)\}\}")
    AUTO_MARKER = "#AUTO#"
    SKIP_MARKER = EnvGenerator.SKIP_MARKER

    @classmethod
    def is_auto_value(cls, value: Optional[str]) -> bool:
        """Возвращает True, если значение является маркером автоопределения #AUTO#."""
        return (value or "").strip() == cls.AUTO_MARKER

    @classmethod
    def is_skip_value(cls, value: Optional[str]) -> bool:
        """Возвращает True, если значение является маркером пропуска #SKIP#."""
        return EnvGenerator.is_skip_value(value)

    @classmethod
    def is_gen_value(cls, value: Optional[str]) -> bool:
        """Возвращает True, если значение является маркером генерации #GEN:...#."""
        return EnvGenerator.is_gen_marker(value)

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
                    if default_val.startswith("default="):
                        default_val = default_val[len("default=") :].strip()
            notices.append(notice)
            return default_val

        resolved_val = cls.PROMPT_RE.sub(_replace, raw_val)
        return True, "; ".join(notices), resolved_val

    @classmethod
    def split_value_and_comment(cls, raw_rhs: str) -> Tuple[str, str, bool]:
        """
        Отделяет значение от хвостового комментария (# ... вне кавычек).
        Не разрывает специальные маркеры #AUTO#, #SKIP#, #GEN:...#.
        Возвращает (unquoted_value, inline_comment, was_quoted).
        """
        rhs = raw_rhs.strip()
        if not rhs:
            return "", "", False

        if rhs[0] in ('"', "'"):
            quote = rhs[0]
            escaped = False
            for idx in range(1, len(rhs)):
                ch = rhs[idx]
                if escaped:
                    escaped = False
                    continue
                if ch == "\\" and quote == '"':
                    escaped = True
                    continue
                if ch == quote:
                    val = rhs[1:idx]
                    rest = rhs[idx + 1 :].strip()
                    inline_c = rest if rest.startswith("#") else ""
                    return val, inline_c, True
            return rhs[1:], "", True

        # Незакавыченное значение: ищем ' #' (комментарий после пробела), не трогая #AUTO# / #SKIP# / #GEN:...#
        for idx, ch in enumerate(rhs):
            if ch == "#" and idx > 0 and rhs[idx - 1].isspace():
                return rhs[:idx].strip(), rhs[idx:].strip(), False

        return rhs, "", False

    def parse_lines(self, content: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """
        Парсит текст .env.
        Возвращает кортеж: (словарь {ключ: значение}, список распарсенных строк с метаданными и комментариями).
        """
        key_values: Dict[str, str] = {}
        parsed_lines: List[Dict[str, Any]] = []
        pending_leading: List[str] = []

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                pending_leading.clear()
                parsed_lines.append({"type": "blank", "raw": line})
                continue
            if stripped.startswith("#"):
                pending_leading.append(line)
                parsed_lines.append({"type": "comment", "raw": line})
                continue

            if "=" in line:
                key, val_part = line.split("=", 1)
                k = key.strip()
                unquoted_val, inline_c, was_quoted = self.split_value_and_comment(val_part)
                is_skipped = self.is_skip_value(unquoted_val) or (
                    unquoted_val == "" and self.SKIP_MARKER in inline_c
                )
                key_values[k] = unquoted_val
                parsed_lines.append(
                    {
                        "type": "pair",
                        "key": k,
                        "value": unquoted_val,
                        "raw": line,
                        "inline_comment": inline_c,
                        "was_quoted": was_quoted,
                        "is_skipped": is_skipped,
                        "leading_comments": list(pending_leading),
                    }
                )
                pending_leading.clear()
            else:
                pending_leading.clear()
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
        Формирует список всех переменных из шаблона .env для редактирования в TUI/CLI,
        накладывая сохраненные значения из локальной папки env/ или установленного файла.
        """
        _, lines = self.parse_file(template_path)
        overrides: Dict[str, str] = {}
        for path in override_paths or []:
            if not path:
                continue
            try:
                is_f = os.path.isfile(path)
            except PermissionError:
                continue
            if is_f:
                _, ov_lines = self.parse_file(path)
                for ov_item in ov_lines:
                    if ov_item["type"] != "pair":
                        continue
                    k = ov_item["key"]
                    v = self.SKIP_MARKER if ov_item.get("is_skipped") else ov_item["value"]
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
                is_auto = self.is_auto_value(current_val) or self.is_auto_value(default_val if has_prompt else raw_val)
                is_skip = self.is_skip_value(current_val)
                is_gen = self.is_gen_value(current_val) or self.is_gen_value(default_val if has_prompt else raw_val)
                entries.append(
                    {
                        "key": k,
                        "value": current_val,
                        "default_value": default_val,
                        "has_prompt": has_prompt,
                        "required_prompt": bool(has_prompt and default_val == ""),
                        "is_auto": is_auto,
                        "is_skip": is_skip,
                        "is_gen": is_gen,
                        "notice": notice or comment_str,
                        "comment": comment_str,
                    }
                )
        return entries

    @classmethod
    def _format_assignment(cls, key: str, val: str, prefer_quotes: bool = False, inline_comment: str = "") -> str:
        needs_quotes = (
            prefer_quotes
            or (" " in val and not (val.startswith('"') and val.endswith('"')))
            or cls.is_auto_value(val)
            or cls.is_skip_value(val)
            or cls.is_gen_value(val)
            or ("#" in val)
        )
        body = f'{key}="{val}"' if needs_quotes else f"{key}={val}"
        if inline_comment:
            return f"{body}  {inline_comment}"
        return body

    def render_with_values(
        self,
        template_path: str,
        values: Dict[str, str],
        existing_path: Optional[str] = None,
    ) -> str:
        """
        Генерирует текст .env на базе структуры и комментариев шаблона,
        сохраняя инлайн-комментарии и дополнительные пользовательские строки/комментарии из existing_path.
        """
        _, lines = self.parse_file(template_path)
        existing_inline: Dict[str, str] = {}
        extra_user_lines: List[str] = []
        template_keys = {item["key"] for item in lines if item["type"] == "pair"}

        if existing_path and os.path.isfile(existing_path):
            _, ex_lines = self.parse_file(existing_path)
            for ex_item in ex_lines:
                if ex_item["type"] == "pair":
                    ek = ex_item["key"]
                    if ex_item.get("inline_comment"):
                        existing_inline[ek] = ex_item["inline_comment"]
                    if ek not in template_keys and ek not in values:
                        extra_user_lines.extend(ex_item.get("leading_comments", []))
                        extra_user_lines.append(ex_item["raw"])

        out_lines: List[str] = []
        seen_keys = set()

        for item in lines:
            if item["type"] == "pair":
                k = item["key"]
                seen_keys.add(k)
                inline_c = item.get("inline_comment") or existing_inline.get(k, "")
                if self.SKIP_MARKER in inline_c and not self.is_skip_value(values.get(k, item["value"])):
                    inline_c = ""
                prefer_q = bool(item.get("was_quoted"))
                if k in values:
                    out_lines.append(self._format_assignment(k, values[k], prefer_quotes=prefer_q, inline_comment=inline_c))
                else:
                    _, _, def_val = self.extract_prompt_info(item["value"])
                    out_lines.append(self._format_assignment(k, def_val, prefer_quotes=prefer_q, inline_comment=inline_c))
            else:
                out_lines.append(item["raw"])

        for k, val in values.items():
            if k not in seen_keys:
                out_lines.append(self._format_assignment(k, val, inline_comment=existing_inline.get(k, "")))

        if extra_user_lines:
            out_lines.append("")
            out_lines.extend(extra_user_lines)

        return "\n".join(out_lines) + "\n"
