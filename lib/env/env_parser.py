"""
Parser for environment (.env) files preserving comments and structure.
"""
from typing import Any, Dict, List, Tuple


class EnvParser:
    """Парсер .env файлов с сохранением структуры строк и комментариев."""

    def parse_lines(self, content: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
        """
        Парсит текст .env.
        Возвращает кортеж:
        (словарь {ключ: значение}, список распарсенных строк с метаданными).
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
                # Удаляем внешние кавычки, если они есть
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
