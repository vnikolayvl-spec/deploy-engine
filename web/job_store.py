"""Хранилище фоновых задач и истории аудита планов веб-модуля Deploy Engine (0600, блокировка 1 live-задачи)."""

from __future__ import annotations

import datetime
import json
import os
import re
import secrets
import signal
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

JOB_ID_RE = re.compile(r"^job_[0-9]{8}_[0-9]{6}_[a-f0-9]{6}$")
MAX_HISTORY_JOBS = 100


class JobStore:
    """Управляет жизненным циклом, NDJSON-логами, lock-файлом и безопасной отменой (SIGINT) фоновых задач."""

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = Path(base_dir).resolve() if base_dir else self._resolve_default_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.base_dir, 0o700)
        except OSError:
            pass

    @staticmethod
    def _resolve_default_dir() -> Path:
        candidates = [
            Path("/var/lib/de_deploy-engine/web_jobs"),
            Path.home() / ".local" / "state" / "deploy-engine" / "web_jobs",
            Path(tempfile.gettempdir()) / "de_deploy-engine_web_jobs",
        ]
        for cand in candidates:
            try:
                cand.mkdir(parents=True, exist_ok=True)
                probe = cand / ".write_probe"
                probe.write_text("ok", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return cand.resolve()
            except OSError:
                continue
        return candidates[-1].resolve()

    def _safe_path(self, job_id: str, suffix: str) -> Path:
        clean = (job_id or "").strip()
        if not JOB_ID_RE.match(clean):
            raise ValueError(f"Некорректный идентификатор задачи: '{job_id}'")
        resolved = (self.base_dir / f"{clean}{suffix}").resolve()
        base_str = str(self.base_dir)
        if not str(resolved).startswith(base_str + os.sep):
            raise ValueError("Запрещенный путь к файлу задачи.")
        return resolved

    @staticmethod
    def _write_json_atomic(path: Path, data: Dict[str, Any]) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=".job_", suffix=".tmp", dir=str(path.parent))
        try:
            os.chmod(tmp_name, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp_name, path)
            os.chmod(path, 0o600)
        except Exception:
            if os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
            raise

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if pid <= 1:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def get_active_job_id(self) -> Optional[str]:
        """Возвращает job_id текущей активной задачи (если процесс воркера жив), иначе очищает устаревший lock."""
        lock_path = self.base_dir / "active_live.lock"
        if not lock_path.is_file():
            return None
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            job_id = str(data.get("job_id") or "")
            pid = int(data.get("pid") or 0)
            rec = self.read_job(job_id) if job_id and JOB_ID_RE.match(job_id) else None
            if rec and rec.get("status") in ("queued", "running") and (pid == 0 or self._is_pid_alive(pid)):
                return job_id
        except Exception:
            pass
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None

    def acquire_live_lock(self, job_id: str, pid: int = 0) -> None:
        lock_path = self.base_dir / "active_live.lock"
        self._write_json_atomic(lock_path, {"job_id": job_id, "pid": pid})

    def release_live_lock(self, job_id: str) -> None:
        lock_path = self.base_dir / "active_live.lock"
        if not lock_path.is_file():
            return
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            if data.get("job_id") == job_id:
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    def create_job(
        self,
        plan: Dict[str, Any],
        ordered_packages: List[str],
        actor: Dict[str, Any],
        mode: str,
    ) -> Dict[str, Any]:
        """Создаёт запись новой фоновой задачи и пустой NDJSON-лог."""
        ts_slug = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        job_id = f"job_{ts_slug}_{secrets.token_hex(3)}"
        now_iso = datetime.datetime.now().isoformat(timespec="seconds")
        record: Dict[str, Any] = {
            "job_id": job_id,
            "status": "queued",
            "mode": mode,
            "actor": {
                "username": str(actor.get("username") or "unknown"),
                "role": str(actor.get("role") or "unknown"),
            },
            "created_at": now_iso,
            "started_at": None,
            "finished_at": None,
            "duration_sec": 0.0,
            "pid": None,
            "pgid": None,
            "phase": "Подготовка к запуску",
            "error": None,
            "ordered_packages": list(ordered_packages),
            "package_statuses": {pkg: "queued" for pkg in ordered_packages},
            "plan": plan,
            "events_count": 0,
        }
        self._write_json_atomic(self._safe_path(job_id, ".json"), record)
        log_path = self._safe_path(job_id, ".ndjson")
        log_path.touch(exist_ok=True)
        try:
            os.chmod(log_path, 0o600)
        except OSError:
            pass
        self._prune_old_jobs()
        return record

    def read_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        path = self._safe_path(job_id, ".json")
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def update_job(self, job_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        rec = self.read_job(job_id)
        if not rec:
            raise ValueError(f"Задача '{job_id}' не найдена.")
        rec.update(patch)
        self._write_json_atomic(self._safe_path(job_id, ".json"), rec)
        return rec

    def append_event(self, job_id: str, line: str, pkg: Optional[str] = None, level: str = "info") -> None:
        log_path = self._safe_path(job_id, ".ndjson")
        evt = {
            "ts": datetime.datetime.now().strftime("%H:%M:%S"),
            "pkg": pkg or "",
            "level": level,
            "line": str(line),
        }
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(evt, ensure_ascii=False) + "\n")

    def read_events(self, job_id: str, offset: int = 0, limit: int = 600) -> Tuple[List[Dict[str, Any]], int]:
        log_path = self._safe_path(job_id, ".ndjson")
        if not log_path.is_file():
            return [], 0
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lines)
        start = max(0, min(int(offset), total))
        end = min(total, start + max(1, min(int(limit), 2000)))
        events: List[Dict[str, Any]] = []
        for raw in lines[start:end]:
            try:
                events.append(json.loads(raw))
            except Exception:
                events.append({"ts": "", "pkg": "", "level": "info", "line": raw})
        return events, end

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("job_*.json"), reverse=True):
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "job_id": rec.get("job_id"),
                    "status": rec.get("status"),
                    "mode": rec.get("mode"),
                    "actor": rec.get("actor"),
                    "created_at": rec.get("created_at"),
                    "started_at": rec.get("started_at"),
                    "finished_at": rec.get("finished_at"),
                    "duration_sec": rec.get("duration_sec", 0.0),
                    "phase": rec.get("phase", ""),
                    "error": rec.get("error"),
                    "ordered_packages": rec.get("ordered_packages", []),
                    "package_statuses": rec.get("package_statuses", {}),
                    "plan_summary": rec.get("plan", {}).get("actions", {}),
                })
                if len(items) >= max(1, min(int(limit), MAX_HISTORY_JOBS)):
                    break
            except Exception:
                continue
        return items

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Безопасно отправляет SIGINT группе процессов активного воркера для LIFO-отката."""
        rec = self.read_job(job_id)
        if not rec:
            raise ValueError(f"Задача '{job_id}' не найдена.")
        if rec.get("status") not in ("queued", "running"):
            return {"job_id": job_id, "cancelled": False, "status": rec.get("status"), "message": "Задача уже завершена."}

        pid = int(rec.get("pid") or 0)
        pgid = int(rec.get("pgid") or 0)
        self.append_event(job_id, "❗ Получен запрос на отмену задачи — отправка SIGINT для LIFO-отката...", level="warning")
        if pgid > 1 and self._is_pid_alive(pid):
            try:
                os.killpg(pgid, signal.SIGINT)
            except ProcessLookupError:
                pass
            return {"job_id": job_id, "cancelled": True, "status": "cancelling", "message": "Отправлен сигнал SIGINT."}

        now_iso = datetime.datetime.now().isoformat(timespec="seconds")
        self.update_job(job_id, {"status": "cancelled", "finished_at": now_iso, "phase": "Отменено"})
        self.release_live_lock(job_id)
        return {"job_id": job_id, "cancelled": True, "status": "cancelled", "message": "Задача помечена как отмененная."}

    def _prune_old_jobs(self) -> None:
        all_files = sorted(self.base_dir.glob("job_*.json"), reverse=True)
        for old_json in all_files[MAX_HISTORY_JOBS:]:
            try:
                old_json.unlink(missing_ok=True)
                old_json.with_suffix(".ndjson").unlink(missing_ok=True)
            except OSError:
                pass
