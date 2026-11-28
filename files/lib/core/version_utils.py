"""
Утилиты SemVer-версионирования движка и пакетов Deploy Engine v3.0.0:
разбор версий, сравнение, проверка ограничений (>=, <=, >, <, ==, !=, ~=) и min_engine_version.
"""
import os
import re
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_ENGINE_VERSION = "3.1.0"

_SEMVER_RE = re.compile(
    r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?\s*$"
)
_REQ_SPLIT_RE = re.compile(r"^([A-Za-z0-9_./-]+)\s*(.*)$")
_CONSTRAINT_RE = re.compile(r"^(>=|<=|!=|==|~=|~=|>|<)\s*(.+)$")


def get_engine_version() -> str:
    """Возвращает текущую версию Deploy Engine из VERSION.txt (fallback: 3.1.0)."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.normpath(os.path.join(here, "..", "..", "..", "VERSION.txt")),
        os.path.normpath(os.path.join(here, "..", "..", "VERSION.txt")),
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read().strip()
                if text:
                    return text
            except OSError:
                continue
    return DEFAULT_ENGINE_VERSION


def parse_semver(version_str: Optional[str]) -> Tuple[int, int, int, int, str]:
    """
    Парсит SemVer-строку в кортеж (major, minor, patch, is_release, prerelease_str).
    is_release = 1 для финального релиза, 0 для pre-release (1.0.0-rc1 < 1.0.0).
    """
    raw = str(version_str or "0.0.0").strip()
    match = _SEMVER_RE.match(raw)
    if not match:
        return (0, 0, 0, 0, raw)
    major = int(match.group(1) or 0)
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)
    pre = match.group(4) or ""
    return (major, minor, patch, 0 if pre else 1, pre)


def compare_semver(v1: Optional[str], v2: Optional[str]) -> int:
    """Сравнивает две SemVer-версии: -1 если v1 < v2, 0 если равны, 1 если v1 > v2."""
    p1 = parse_semver(v1)
    p2 = parse_semver(v2)
    if p1[:4] != p2[:4]:
        return -1 if p1[:4] < p2[:4] else 1
    if p1[4] == p2[4]:
        return 0
    return -1 if p1[4] < p2[4] else 1


def parse_requirement(spec: str) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Разбирает спецификацию зависимости, например:
    'de-lib>=1.0.0,<2.0.0' -> ('de-lib', [('>=', '1.0.0'), ('<', '2.0.0')])
    'core/de-lib' -> ('core/de-lib', [])
    """
    clean = str(spec or "").strip()
    if not clean:
        return "", []
    match = _REQ_SPLIT_RE.match(clean)
    if not match:
        return clean, []
    pkg_name = match.group(1).strip()
    rest = match.group(2).strip()
    if not rest:
        return pkg_name, []

    constraints: List[Tuple[str, str]] = []
    for part in rest.split(","):
        item = part.strip()
        if not item:
            continue
        c_match = _CONSTRAINT_RE.match(item)
        if c_match:
            constraints.append((c_match.group(1), c_match.group(2).strip()))
    return pkg_name, constraints


def satisfies_constraints(version_str: str, constraints: List[Tuple[str, str]]) -> bool:
    """Проверяет, удовлетворяет ли версия списку SemVer-ограничений."""
    if not constraints:
        return True
    for op, target_ver in constraints:
        cmp_val = compare_semver(version_str, target_ver)
        if op == ">=" and cmp_val < 0:
            return False
        if op == "<=" and cmp_val > 0:
            return False
        if op == ">" and cmp_val <= 0:
            return False
        if op == "<" and cmp_val >= 0:
            return False
        if op == "==" and cmp_val != 0:
            return False
        if op == "!=" and cmp_val == 0:
            return False
        if op == "~=":
            # Совместимый релиз: >= target_ver и < (major, minor+1, 0) для X.Y.Z или < (major+1, 0, 0) для X.Y
            if cmp_val < 0:
                return False
            parts = [p for p in str(target_ver).lstrip("v").split("-")[0].split(".") if p.isdigit()]
            t_major, t_minor, _ = parse_semver(target_ver)[:3]
            upper = f"{t_major + 1}.0.0" if len(parts) <= 2 else f"{t_major}.{t_minor + 1}.0"
            if compare_semver(version_str, upper) >= 0:
                return False
    return True


def format_constraints(constraints: List[Tuple[str, str]]) -> str:
    """Форматирует список ограничений обратно в строку вида '>=1.0.0,<2.0.0'."""
    return ",".join(f"{op}{ver}" for op, ver in constraints)


def version_status(installed_ver: Optional[str], available_ver: Optional[str]) -> str:
    """
    Возвращает статус версии пакета:
    'not_installed' | 'upgrade' | 'current' | 'downgrade'.
    """
    if not installed_ver:
        return "not_installed"
    if not available_ver:
        return "current"
    cmp_val = compare_semver(installed_ver, available_ver)
    if cmp_val < 0:
        return "upgrade"
    if cmp_val > 0:
        return "downgrade"
    return "current"


def check_min_engine_version(
    pkg_data: Dict[str, Any],
    current_engine_version: Optional[str] = None,
) -> Tuple[bool, str]:
    """Проверяет поле min_engine_version в манифесте пакета."""
    min_ver = str((pkg_data or {}).get("min_engine_version") or "").strip()
    if not min_ver:
        return True, ""
    cur_ver = current_engine_version or get_engine_version()
    if compare_semver(cur_ver, min_ver) < 0:
        pkg_name = (pkg_data or {}).get("name", "unknown")
        return (
            False,
            f"Пакет '{pkg_name}' требует Deploy Engine >= v{min_ver}, текущая версия: v{cur_ver}.",
        )
    return True, ""
