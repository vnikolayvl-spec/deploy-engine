"""
Automatic converter from systemd (.service, .timer) and .env files to macOS launchd XML .plist.
"""
import os
import plistlib
import re
import shlex
from typing import Any, Dict, List, Optional


class SystemdToPlistConverter:
    """
    Автоматический конвертер файлов systemd (.service, .timer) и переменных окружения (.env)
    в валидный XML .plist для macOS launchd со статической секцией EnvironmentVariables.
    """

    LABEL_PREFIX = "com.deploy-engine"

    @classmethod
    def get_service_stem(cls, unit_name: str) -> str:
        """Возвращает базовое имя службы без расширения .service / .timer / .plist."""
        clean = os.path.basename(unit_name.split(":")[-1])
        for ext in (".service", ".timer", ".plist"):
            if clean.endswith(ext):
                return clean[: -len(ext)]
        return clean

    @classmethod
    def get_plist_label(cls, pkg_name: str, unit_name: str) -> str:
        """Генерирует уникальный Label для launchd: com.deploy-engine.<pkg>.<stem>."""
        stem = cls.get_service_stem(unit_name)
        safe_pkg = re.sub(r"[^a-zA-Z0-9_.-]", "-", pkg_name)
        safe_stem = re.sub(r"[^a-zA-Z0-9_.-]", "-", stem)
        return f"{cls.LABEL_PREFIX}.{safe_pkg}.{safe_stem}"

    @classmethod
    def get_plist_filename(cls, pkg_name: str, unit_name: str) -> str:
        """Генерирует имя файла .plist."""
        return f"{cls.get_plist_label(pkg_name, unit_name)}.plist"

    @staticmethod
    def parse_ini_sections(text: str) -> Dict[str, Dict[str, List[str]]]:
        """Парсит INI-подобный файл systemd (.service или .timer) по секциям."""
        sections: Dict[str, Dict[str, List[str]]] = {}
        current_section = "DEFAULT"
        sections[current_section] = {}

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                sections.setdefault(current_section, {})
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                key = k.strip()
                val = v.strip()
                sections[current_section].setdefault(key, []).append(val)
        return sections

    @staticmethod
    def parse_env_text(text: str) -> Dict[str, str]:
        """Парсит содержимое .env файла в словарь статических переменных окружения."""
        env_vars: Dict[str, str] = {}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            val = v.strip()
            if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
                val = val[1:-1]
            if key:
                env_vars[key] = val
        return env_vars

    @classmethod
    def parse_env_file(cls, env_path: Optional[str]) -> Dict[str, str]:
        """Читает .env файл с диска и возвращает словарь переменных."""
        if not env_path or not os.path.isfile(env_path):
            return {}
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                return cls.parse_env_text(f.read())
        except Exception:
            return {}

    @staticmethod
    def parse_systemd_duration(duration_str: str) -> Optional[int]:
        """Переводит интервал systemd (например, '30s', '15m', '2h', '1d') в секунды."""
        raw = duration_str.strip().lower()
        if not raw:
            return None
        if raw.isdigit():
            return int(raw)

        multipliers = {
            "us": 0,
            "ms": 0,
            "s": 1,
            "sec": 1,
            "second": 1,
            "seconds": 1,
            "m": 60,
            "min": 60,
            "minute": 60,
            "minutes": 60,
            "h": 3600,
            "hr": 3600,
            "hour": 3600,
            "hours": 3600,
            "d": 86400,
            "day": 86400,
            "days": 86400,
            "w": 604800,
            "week": 604800,
        }
        total_seconds = 0
        matched = False
        for amount_str, unit in re.findall(r"(\d+)\s*([a-z]+)?", raw):
            matched = True
            amount = int(amount_str)
            mult = multipliers.get(unit or "s", 1)
            total_seconds += amount * mult
        return total_seconds if matched and total_seconds > 0 else None

    @staticmethod
    def parse_on_calendar(calendar_expr: str) -> Optional[Dict[str, int]]:
        """Конвертирует выражение OnCalendar в словарь StartCalendarInterval для launchd."""
        expr = calendar_expr.strip().lower()
        presets: Dict[str, Dict[str, int]] = {
            "hourly": {"Minute": 0},
            "daily": {"Hour": 0, "Minute": 0},
            "weekly": {"Weekday": 1, "Hour": 0, "Minute": 0},
            "monthly": {"Day": 1, "Hour": 0, "Minute": 0},
        }
        if expr in presets:
            return dict(presets[expr])

        # Формат вида '*-*-* 03:30:00' или 'Mon *-*-* 04:15:00'
        time_match = re.search(r"(\d{1,2}|\*):(\d{1,2}|\*)(?::\d{1,2}|\*)?", expr)
        if time_match:
            cal: Dict[str, int] = {}
            h_str, m_str = time_match.group(1), time_match.group(2)
            if h_str.isdigit():
                cal["Hour"] = int(h_str)
            if m_str.isdigit():
                cal["Minute"] = int(m_str)
            return cal if cal else {"Minute": 0}
        return None

    @classmethod
    def _parse_exec_start(cls, exec_cmd: str) -> List[str]:
        """Преобразует строку ExecStart в массив ProgramArguments."""
        cleaned = exec_cmd.strip()
        while cleaned and cleaned[0] in ("-", "@", "+", "!", ":"):
            cleaned = cleaned[1:].strip()

        if any(op in cleaned for op in ("|", "&&", "||", ";", ">", "<", "$(")):
            return ["/bin/bash", "-c", cleaned]
        try:
            args = shlex.split(cleaned)
            return args if args else ["/bin/bash", "-c", cleaned]
        except ValueError:
            return ["/bin/bash", "-c", cleaned]

    @classmethod
    def build_plist_dict(
        cls,
        pkg_name: str,
        unit_name: str,
        service_text: str,
        timer_text: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        context_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Собирает структуру словаря launchd .plist из .service, .timer и статических переменных .env."""
        macros = context_vars or {}
        rendered_service = service_text
        for marker, real_val in macros.items():
            rendered_service = rendered_service.replace(marker, real_val)

        sections = cls.parse_ini_sections(rendered_service)
        srv_sec = sections.get("Service", {})

        label = cls.get_plist_label(pkg_name, unit_name)
        plist_data: Dict[str, Any] = {"Label": label}

        # 1. ProgramArguments из ExecStart
        exec_starts = srv_sec.get("ExecStart", [])
        if exec_starts:
            plist_data["ProgramArguments"] = cls._parse_exec_start(exec_starts[-1])
        else:
            plist_data["ProgramArguments"] = ["/usr/bin/true"]

        # 2. WorkingDirectory, UserName, GroupName
        if "WorkingDirectory" in srv_sec and srv_sec["WorkingDirectory"]:
            plist_data["WorkingDirectory"] = srv_sec["WorkingDirectory"][-1]
        if "User" in srv_sec and srv_sec["User"]:
            plist_data["UserName"] = srv_sec["User"][-1]
        if "Group" in srv_sec and srv_sec["Group"]:
            plist_data["GroupName"] = srv_sec["Group"][-1]

        # 3. Статическая секция EnvironmentVariables (из .env + Environment= в .service)
        merged_env: Dict[str, str] = dict(env_vars or {})
        for env_line in srv_sec.get("Environment", []):
            for token in shlex.split(env_line):
                if "=" in token:
                    k, v = token.split("=", 1)
                    merged_env[k.strip()] = v.strip()

        for ek, ev in list(merged_env.items()):
            for marker, real_val in macros.items():
                ev = ev.replace(marker, real_val)
            merged_env[ek] = ev

        if merged_env:
            plist_data["EnvironmentVariables"] = merged_env

        # 4. Расписание из .timer (если передан) или поведение демона из .service
        has_timer_schedule = False
        if timer_text:
            rendered_timer = timer_text
            for marker, real_val in macros.items():
                rendered_timer = rendered_timer.replace(marker, real_val)
            t_sec = cls.parse_ini_sections(rendered_timer).get("Timer", {})

            for interval_key in ("OnUnitActiveSec", "OnActiveSec", "OnBootSec", "OnStartupSec"):
                if interval_key in t_sec and t_sec[interval_key]:
                    seconds = cls.parse_systemd_duration(t_sec[interval_key][-1])
                    if seconds:
                        plist_data["StartInterval"] = seconds
                        has_timer_schedule = True
                        break

            if "OnCalendar" in t_sec and t_sec["OnCalendar"]:
                cal_dict = cls.parse_on_calendar(t_sec["OnCalendar"][-1])
                if cal_dict:
                    plist_data["StartCalendarInterval"] = cal_dict
                    has_timer_schedule = True

        if not has_timer_schedule:
            plist_data["RunAtLoad"] = True
            restart_policy = (srv_sec.get("Restart", ["no"])[-1]).lower()
            if restart_policy == "always":
                plist_data["KeepAlive"] = True
            elif restart_policy in ("on-failure", "on-abnormal", "on-abort"):
                plist_data["KeepAlive"] = {"SuccessfulExit": False}

        return plist_data

    @classmethod
    def convert_to_xml(
        cls,
        pkg_name: str,
        unit_name: str,
        service_text: str,
        timer_text: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        context_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """Конвертирует данные .service, .timer и .env в XML-строку формата Apple plist."""
        plist_dict = cls.build_plist_dict(
            pkg_name=pkg_name,
            unit_name=unit_name,
            service_text=service_text,
            timer_text=timer_text,
            env_vars=env_vars,
            context_vars=context_vars,
        )
        return plistlib.dumps(plist_dict, fmt=plistlib.FMT_XML, sort_keys=False).decode("utf-8")
