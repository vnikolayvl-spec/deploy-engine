#!/usr/bin/env python3
"""Точка входа бэкенд-плагина Deploy Engine для de-web (протокол v2: JSON stdin -> JSON stdout)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

WEB_DIR = Path(__file__).resolve().parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from engine_bridge import EngineBridge  # noqa: E402
from env_service import EnvWebService  # noqa: E402
from job_store import JobStore  # noqa: E402

ROUTE_PERMISSIONS: Dict[str, str] = {
    "get_state": "view",
    "preview_plan": "view",
    "get_package_details": "view",
    "get_package_logs": "logs.read",
    "restart_service": "service.control",
    "inspect_env": "env.read",
    "get_env_form": "env.read",
    "save_env_preset": "env.write",
    "sync_packages": "repo.sync",
    "start_job": "view",
    "get_job_status": "logs.read",
    "list_jobs": "logs.read",
    "cancel_job": "jobs.cancel",
}


class DeployEngineWebApi:
    """Диспетчер маршрутов веб-модуля Deploy Engine со строгой проверкой ACL и изоляцией фоновых задач."""

    def __init__(self, jobs_dir: Optional[str] = None, search_roots: Optional[List[str]] = None) -> None:
        self.bridge = EngineBridge(search_roots=search_roots)
        self.env_service = EnvWebService(self.bridge)
        self.job_store = JobStore(base_dir=jobs_dir)
        self.search_roots = search_roots

    @staticmethod
    def _has_perm(perms: Set[str], required: str) -> bool:
        return "*" in perms or required in perms

    def _spawn_worker(self, job_id: str) -> int:
        worker_script = str(WEB_DIR / "job_worker.py")
        cmd = [sys.executable, worker_script, job_id, str(self.job_store.base_dir)]
        if self.search_roots:
            cmd.append(self.search_roots[0])
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        return int(proc.pid)

    def _handle_start_job(self, payload: Dict[str, Any], user: Dict[str, Any], perms: Set[str]) -> Dict[str, Any]:
        plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
        opts = plan.get("options") if isinstance(plan.get("options"), dict) else {}
        is_sandbox = bool(opts.get("sandbox"))
        is_dry_run = bool(opts.get("dry_run"))
        has_backups = bool(plan.get("backups") or plan.get("restores"))
        has_mutations = bool(plan.get("actions") or plan.get("unit_updates"))

        if not has_mutations and not has_backups:
            return {"ok": False, "error": "План пуст — выберите хотя бы одно действие."}

        if is_sandbox or is_dry_run:
            if not (self._has_perm(perms, "plan.execute") or self._has_perm(perms, "sandbox.run")):
                return {"ok": False, "error": "Недостаточно прав для запуска Sandbox/Dry-Run (требуется 'sandbox.run')."}
            mode = "dry_run" if is_dry_run else "sandbox"
        else:
            if has_mutations and not self._has_perm(perms, "plan.execute"):
                return {"ok": False, "error": "Недостаточно прав для боевого выполнения плана (требуется 'plan.execute')."}
            if has_backups and not (self._has_perm(perms, "backup.manage") or self._has_perm(perms, "plan.execute")):
                return {"ok": False, "error": "Недостаточно прав для операций резервного копирования (требуется 'backup.manage')."}
            mode = "live"

        if mode == "live":
            active_id = self.job_store.get_active_job_id()
            if active_id:
                return {
                    "ok": False,
                    "error": f"Уже выполняется активная задача '{active_id}'. Дождитесь завершения или отмените её.",
                    "data": {"active_job_id": active_id},
                }

        preview = self.bridge.preview_plan(plan)
        if preview.get("warnings"):
            return {"ok": False, "error": "; ".join(preview["warnings"])}
        if preview.get("requires_env_wizard") and not is_dry_run:
            pending = [e["package"] for e in preview.get("env_checks", []) if e.get("needs_confirmation")]
            return {
                "ok": False,
                "error": f"Требуется подтвердить .env перед запуском: {', '.join(pending)}",
                "data": {"requires_env_wizard": True, "env_checks": preview["env_checks"]},
            }

        ordered = list(preview.get("ordered_packages") or [])
        job = self.job_store.create_job(plan=plan, ordered_packages=ordered, actor=user, mode=mode)
        if mode == "live":
            self.job_store.acquire_live_lock(job["job_id"], pid=0)
        pid = self._spawn_worker(job["job_id"])
        self.job_store.update_job(job["job_id"], {"pid": pid})
        if mode == "live":
            self.job_store.acquire_live_lock(job["job_id"], pid=pid)
        return {
            "ok": True,
            "data": {"job_id": job["job_id"], "mode": mode, "ordered_packages": ordered},
            "audit": f"Запущена задача Deploy Engine ({mode}): {', '.join(ordered) or 'план'}",
        }

    def handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action = str(context.get("action") or "").strip()
        payload = context.get("payload") if isinstance(context.get("payload"), dict) else {}
        user = context.get("user") if isinstance(context.get("user"), dict) else {}
        perms: Set[str] = {str(p) for p in (user.get("permissions") or [])}

        req_perm = ROUTE_PERMISSIONS.get(action)
        if req_perm is None:
            return {"ok": False, "error": f"Неизвестный маршрут модуля deploy-engine: '{action}'"}
        if not self._has_perm(perms, req_perm):
            return {"ok": False, "error": f"Недостаточно прав (требуется '{req_perm}')"}

        try:
            sb = bool(payload.get("sandbox"))
            sb_os = payload.get("sandbox_os")

            if action == "get_state":
                active_id = self.job_store.get_active_job_id()
                return {"ok": True, "data": self.bridge.get_state(sandbox=sb, sandbox_os=sb_os, active_job_id=active_id)}

            if action == "preview_plan":
                plan = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
                return {"ok": True, "data": self.bridge.preview_plan(plan)}

            if action == "get_package_details":
                info = self.bridge.get_package_details(str(payload.get("package") or ""), sandbox=sb, sandbox_os=sb_os)
                if not info:
                    return {"ok": False, "error": "Пакет не найден."}
                return {"ok": True, "data": info}

            if action == "get_package_logs":
                return {"ok": True, "data": self.bridge.get_package_logs(str(payload.get("package") or ""), sandbox=sb, sandbox_os=sb_os)}

            if action == "restart_service":
                pkg = str(payload.get("package") or "")
                res = self.bridge.restart_service(pkg, sandbox=sb, sandbox_os=sb_os)
                return {"ok": True, "data": res, "audit": f"Перезапущена служба пакета '{pkg}'"}

            if action == "inspect_env":
                reveal = bool(payload.get("reveal"))
                if reveal and not self._has_perm(perms, "env.reveal"):
                    return {"ok": False, "error": "Недостаточно прав для раскрытия секретов (требуется 'env.reveal')."}
                rep = self.env_service.inspect_env(
                    str(payload.get("package") or ""), reveal=reveal, preset=bool(payload.get("preset")), sandbox=sb, sandbox_os=sb_os
                )
                return {"ok": True, "data": rep}

            if action == "get_env_form":
                reveal = bool(payload.get("reveal")) and self._has_perm(perms, "env.reveal")
                form = self.env_service.get_env_form(str(payload.get("package") or ""), reveal=reveal, sandbox=sb, sandbox_os=sb_os)
                return {"ok": True, "data": form}

            if action == "save_env_preset":
                apply_sys = bool(payload.get("apply_system"))
                if apply_sys and not sb and not self._has_perm(perms, "plan.execute"):
                    return {"ok": False, "error": "Для записи в системный .env требуется право 'plan.execute'."}
                pkg = str(payload.get("package") or "")
                res = self.env_service.save_env_preset(
                    pkg, payload.get("values") or {}, apply_system=apply_sys, sandbox=sb, sandbox_os=sb_os
                )
                return {"ok": True, "data": res, "audit": f"Обновлен .env пресет пакета '{pkg}'" + (" (применен в систему)" if apply_sys else "")}

            if action == "sync_packages":
                res = self.bridge.sync_packages()
                return {"ok": True, "data": res, "audit": f"Обновлен репозиторий пакетов ({res['packages_count']} пакетов)"}

            if action == "start_job":
                return self._handle_start_job(payload, user, perms)

            if action == "get_job_status":
                job_id = str(payload.get("job_id") or "")
                rec = self.job_store.read_job(job_id)
                if not rec:
                    return {"ok": False, "error": f"Задача '{job_id}' не найдена."}
                events, next_offset = self.job_store.read_events(job_id, offset=int(payload.get("offset") or 0))
                return {"ok": True, "data": {"job": rec, "events": events, "next_offset": next_offset}}

            if action == "list_jobs":
                return {"ok": True, "data": {"jobs": self.job_store.list_jobs(limit=int(payload.get("limit") or 50))}}

            if action == "cancel_job":
                job_id = str(payload.get("job_id") or "")
                res = self.job_store.cancel_job(job_id)
                return {"ok": True, "data": res, "audit": f"Запрошена отмена задачи '{job_id}'"}

            return {"ok": False, "error": f"Необработанный маршрут: '{action}'"}
        except Exception as err:
            return {"ok": False, "error": str(err)}


def main() -> int:
    try:
        raw = sys.stdin.read()
        context = json.loads(raw) if raw.strip() else {}
        if not isinstance(context, dict):
            context = {}
    except Exception as err:
        print(json.dumps({"ok": False, "error": f"Некорректный JSON-запрос: {err}"}, ensure_ascii=False))
        return 0
    result = DeployEngineWebApi().handle(context)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
