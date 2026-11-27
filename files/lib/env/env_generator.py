"""
Генератор параметров #GEN:...# и безопасная материализация маркера #SKIP# для .env (Deploy Engine v3.0.0).
Поддерживает: #GEN#, #GEN:token[:N]#, #GEN:hex[:N]#, #GEN:pass[:N]#, #GEN:pass_strong[:N]#,
#GEN:uuid#, #GEN:b64[:N]#, #GEN:port:MIN-MAX#, а также пасстру #GEN:pkg:<name># для пакетных генераторов.
"""
import base64
import random
import re
import secrets
import socket
import string
import uuid
from typing import Callable, Dict, List, Optional, Tuple


class EnvGenerator:
    """Разрешение маркеров #GEN:...# и безопасная обработка маркера #SKIP#."""

    SKIP_MARKER = "#SKIP#"
    GEN_RE = re.compile(r"^#GEN(?::([A-Za-z0-9_]+)(?::([A-Za-z0-9_.-]+))?)?#$")
    _ALNUM = string.ascii_letters + string.digits
    _TOKEN_CHARS = string.ascii_letters + string.digits + "_-"
    # Символы для надежного пароля без кавычек, пробелов, $ и # (безопасно для shell/.env)
    _STRONG_CHARS = string.ascii_letters + string.digits + "!@%^&*()-_=+[]{}.,:?"

    @classmethod
    def is_skip_value(cls, value: Optional[str]) -> bool:
        """Возвращает True, если значение равно маркеру #SKIP#."""
        return str(value or "").strip() == cls.SKIP_MARKER

    @classmethod
    def is_gen_marker(cls, value: Optional[str]) -> bool:
        """Возвращает True, если значение является маркером генерации #GEN# или #GEN:...#."""
        return bool(cls.GEN_RE.match(str(value or "").strip()))

    @classmethod
    def is_pkg_gen_marker(cls, value: Optional[str]) -> bool:
        """Возвращает True для доменного маркера #GEN:pkg:<name>#, разрешаемого самим пакетом."""
        match = cls.GEN_RE.match(str(value or "").strip())
        return bool(match and (match.group(1) or "").lower() == "pkg")

    @staticmethod
    def _parse_int(raw: Optional[str], default: int, min_v: int = 4, max_v: int = 256) -> int:
        try:
            val = int(str(raw or "").strip())
            return max(min_v, min(max_v, val))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _pick_free_port(min_port: int, max_port: int) -> int:
        lo = max(1024, min(min_port, max_port))
        hi = min(65535, max(min_port, max_port))
        candidates = list(range(lo, hi + 1))
        random.shuffle(candidates)
        for port in candidates[:64]:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("127.0.0.1", port))
                    return port
            except OSError:
                continue
        return secrets.randbelow(hi - lo + 1) + lo

    @classmethod
    def resolve_marker(
        cls,
        raw_val: str,
        pkg_generators: Optional[Dict[str, Callable[[], str]]] = None,
    ) -> Tuple[str, bool]:
        """
        Разворачивает #GEN:...# в сгенерированное значение.
        Возвращает (значение, было_ли_развернуто).
        Для #GEN:pkg:<name># без переданного обработчика возвращает (raw_val, False).
        """
        clean = str(raw_val or "").strip()
        match = cls.GEN_RE.match(clean)
        if not match:
            return raw_val, False

        gen_type = (match.group(1) or "token").lower()
        gen_arg = match.group(2)

        if gen_type == "pkg":
            if pkg_generators and gen_arg and gen_arg in pkg_generators:
                return str(pkg_generators[gen_arg]()), True
            return raw_val, False

        if gen_type == "token":
            length = cls._parse_int(gen_arg, default=32)
            return "".join(secrets.choice(cls._TOKEN_CHARS) for _ in range(length)), True

        if gen_type == "hex":
            length = cls._parse_int(gen_arg, default=32)
            return secrets.token_hex((length + 1) // 2)[:length], True

        if gen_type == "pass":
            length = cls._parse_int(gen_arg, default=20)
            return "".join(secrets.choice(cls._ALNUM) for _ in range(length)), True

        if gen_type == "pass_strong":
            length = cls._parse_int(gen_arg, default=24)
            return "".join(secrets.choice(cls._STRONG_CHARS) for _ in range(length)), True

        if gen_type == "uuid":
            return str(uuid.uuid4()), True

        if gen_type == "b64":
            nbytes = cls._parse_int(gen_arg, default=32, min_v=4, max_v=128)
            return base64.b64encode(secrets.token_bytes(nbytes)).decode("ascii"), True

        if gen_type == "port":
            lo, hi = 10000, 60000
            if gen_arg and "-" in gen_arg:
                parts = gen_arg.split("-", 1)
                lo = cls._parse_int(parts[0], default=10000, min_v=1024, max_v=65535)
                hi = cls._parse_int(parts[1], default=60000, min_v=1024, max_v=65535)
            return str(cls._pick_free_port(lo, hi)), True

        return raw_val, False

    @classmethod
    def materialize_env_text(
        cls,
        content: str,
        for_system: bool = True,
        pkg_generators: Optional[Dict[str, Callable[[], str]]] = None,
    ) -> Tuple[str, List[str]]:
        """
        Проходит по строкам .env:
        - разворачивает стандартные маркеры #GEN:...# (кроме #GEN:pkg:<name># без генератора);
        - при for_system=True безопасно заменяет #SKIP# на пустую строку с комментарием '# #SKIP#',
          чтобы старые bash/python скрипты не воспринимали '#SKIP#' как реальное значение.
        Возвращает (обновленный_текст, список_сгенерированных_ключей).
        """
        from lib.env.env_parser import EnvParser

        out_lines: List[str] = []
        generated_keys: List[str] = []
        _, parsed = EnvParser().parse_lines(content)

        for item in parsed:
            if item["type"] != "pair":
                out_lines.append(item["raw"])
                continue

            key = item["key"]
            val = item["value"]
            inline_c = item.get("inline_comment", "")

            if cls.is_skip_value(val):
                if for_system:
                    suffix = f"  {inline_c}" if (inline_c and cls.SKIP_MARKER in inline_c) else f"  # {cls.SKIP_MARKER}"
                    out_lines.append(f'{key}=""{suffix}')
                else:
                    suffix = f"  {inline_c}" if inline_c else ""
                    out_lines.append(f'{key}="{cls.SKIP_MARKER}"{suffix}')
                continue

            if cls.is_gen_marker(val):
                new_val, resolved = cls.resolve_marker(val, pkg_generators=pkg_generators)
                if resolved:
                    generated_keys.append(key)
                    suffix = f"  {inline_c}" if inline_c else ""
                    out_lines.append(f'{key}="{new_val}"{suffix}')
                    continue

            out_lines.append(item["raw"])

        trailing_nl = "\n" if content.endswith("\n") or out_lines else ""
        return "\n".join(out_lines) + trailing_nl, generated_keys
