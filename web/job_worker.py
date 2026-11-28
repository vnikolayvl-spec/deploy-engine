#!/usr/bin/env python3
"""Фоновый воркер выполнения плана Deploy Engine с потоковым логированием по пакетам и LIFO-откатом по SIGINT."""

from __future__ import annotations

import datetime
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

WEB_DIR = Path(__file__).resolve().parent
if str(WEB_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_DIR))

from engine_bridge import EngineBridge  # noqa: E402
from job_store import JobStore  # noqa: E402
from lib.core.engine import Engine  # noqa: E402
from lib.core.execution_context import ExecutionContext  # noqa: E402


class JobWorker:
    """Выполняет план задачи из JobStore, транслирует логи и пофазовые статусы пакетов, перехватывает SIGINT."""

    def __init__(self, job_id: str, jobs_dir: Optional[str] = None, search_roots: Optional[List[str]] = None) -> None:
        self.job_id = job_id
        self.store = JobStore(base_dir=jobs_dir)
        self.bridge = EngineBridge(search_roots=search_roots)
        self.current_pkg: Optional[str] = None
        self.pkg_statuses: Dict[str, str] = {}

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt(f"Получен сигнал остановки ({signum})")

    def _set_pkg_status(self, pkg: str, status: str, phase: Optional[str] = None) -> None:
        self.pkg_statuses[pkg] = status
        patch: Dict[str, Any] = {"package_statuses": dict(self.pkg_statuses)}
        if phase is not None:
            patch["phase"] = phase
        self.store.update_job(self.job_id, patch)

    def _on_pkg_log(self, pkg: Optional[str], message: str) -> None:
        target_pkg = pkg or self.current_pkg
        for line in str(message).splitlines() or [""]:
            level = "error" if ("💥" in line or "❗" in line or "Ошибка" in line) else ("success" if ("✅" in line or "🎉" in line) else "info")
            self.store.append_event(self.job_id, line, pkg=target_pkg, level=level)

    def _on_pkg_status(self, pkg: str, status: str) -> None:
        if not pkg:
            return
        mapped = "failed" if status == "error" else status
        if mapped == "running":
            self.current_pkg = pkg
        self._set_pkg_status(pkg, mapped, phase=f"{mapped}: {pkg}")

    def _on_phase(self, phase: str) -> None:
        if phase:
            self.store.update_job(self.job_id, {"phase": str(phase)})

    def run(self) -> int:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        rec = self.store.read_job(self.job_id)
        if not rec:
            return 1

        started_ts = time.monotonic()
        pid = os.getpid()
        try:
            pgid = os.getpgid(pid)
        except OSError:
            pgid = pid

        self.pkg_statuses = dict(rec.get("package_statuses") or {})
        self.store.update_job(self.job_id, {
            "status": "running",
            "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "pid": pid,
            "pgid": pgid,
            "phase": "Инициализация движка",
        })
        if rec.get("mode") == "live":
            self.store.acquire_live_lock(self.job_id, pid=pid)

        plan = rec.get("plan") if isinstance(rec.get("plan"), dict) else {}
        opts = plan.get("options") if isinstance(plan.get("options"), dict) else {}
        actions = plan.get("actions") if isinstance(plan.get("actions"), dict) else {}
        unit_updates = plan.get("unit_updates") if isinstance(plan.get("unit_updates"), dict) else {}
        backups = list(plan.get("backups") or [])
        restores = plan.get("restores") if isinstance(plan.get("restores"), dict) else {}
        with_hooks = bool(opts.get("with_hooks"))
        sb_os = self.bridge.resolve_sandbox_os(opts.get("sandbox_os")) if opts.get("sandbox") else None
        sb_dir = opts.get("sandbox_dir") or os.path.join(str(WEB_DIR.parent), ".de_web_sandbox")

        ctx = ExecutionContext(
            dry_run=bool(opts.get("dry_run")),
            purge=bool(opts.get("purge")),
            clean_env=bool(opts.get("clean_env")),
            sandbox=bool(opts.get("sandbox")),
            sandbox_os=sb_os,
            sandbox_dir=sb_dir,
            non_interactive=True,
            comment=str(opts.get("comment") or "Веб-модуль Deploy Engine"),
        )
        ctx.add_pkg_log_listener(self._on_pkg_log)
        ctx.add_pkg_status_listener(self._on_pkg_status)
        ctx.add_phase_listener(self._on_phase)

        eng = Engine(ctx)
        if os.environ.get("DE_PACKAGES_CACHE"):
            eng.registry.cache_manager.cache_file_path = os.environ["DE_PACKAGES_CACHE"]
        if os.environ.get("DE_LOCAL_ENV_DIR"):
            eng.env_manager.local_env_dir = os.environ["DE_LOCAL_ENV_DIR"]
        if os.environ.get("DE_BACKUP_DIR"):
            eng.backup_manager.backup_dir = os.environ["DE_BACKUP_DIR"]
        eng.discover_packages(self.bridge._detect_search_roots(), force_rescan=bool(self.bridge.search_roots))

        final_status = "succeeded"
        err_msg: Optional[str] = None
        try:
            # 1. Резервное копирование
            for pkg_key in backups:
                if eng.registry.has(pkg_key):
                    p_name = eng.registry.get(pkg_key)["name"]
                    self.current_pkg = p_name
                    self._set_pkg_status(p_name, "running", phase=f"Бэкап: {p_name}")
                    eng.backup_packages([p_name], comment=ctx.comment)
                    self._set_pkg_status(p_name, "done")

            # 2. Восстановление из бэкапа
            for pkg_key, selector in restores.items():
                if selector and eng.registry.has(pkg_key):
                    p_name = eng.registry.get(pkg_key)["name"]
                    self.current_pkg = p_name
                    self._set_pkg_status(p_name, "running", phase=f"Восстановление: {p_name}")
                    eng.restore_packages([p_name], selector=str(selector))
                    self._set_pkg_status(p_name, "done")

            # 3. Точечное обновление юнитов
            for pkg_key, u_list in unit_updates.items():
                if u_list and eng.registry.has(pkg_key):
                    p_name = eng.registry.get(pkg_key)["name"]
                    self.current_pkg = p_name
                    self._set_pkg_status(p_name, "running", phase=f"Обновление юнитов: {p_name}")
                    eng.update_units(p_name, unit_names=[str(u) for u in u_list], with_hooks=with_hooks)
                    self._set_pkg_status(p_name, "done")

            # 4. Удаление
            for pkg_key, act in actions.items():
                if act == "uninstall" and eng.registry.has(pkg_key):
                    p_name = eng.registry.get(pkg_key)["name"]
                    self.current_pkg = p_name
                    self._set_pkg_status(p_name, "running", phase=f"Удаление: {p_name}")
                    eng.uninstall_package(p_name)
                    self._set_pkg_status(p_name, "done")

            # 5. Переустановка
            for pkg_key, act in actions.items():
                if act == "reinstall" and eng.registry.has(pkg_key):
                    p_name = eng.registry.get(pkg_key)["name"]
                    self.current_pkg = p_name
                    self._set_pkg_status(p_name, "running", phase=f"Переустановка: {p_name}")
                    eng.reinstall_package(p_name)
                    self._set_pkg_status(p_name, "done")

            # 6. SemVer-обновление
            to_upgrade = [k for k, act in actions.items() if act == "upgrade" and eng.registry.has(k)]
            if to_upgrade:
                self.current_pkg = None
                self.store.update_job(self.job_id, {"phase": f"Обновление ({len(to_upgrade)} пак.)"})
                eng.upgrade_packages(to_upgrade)
                for k in to_upgrade:
                    p_name = eng.registry.get(k)["name"]
                    if self.pkg_statuses.get(p_name) in ("queued", "running"):
                        self.pkg_statuses[p_name] = "done"

            # 7. Установка с графом зависимостей
            to_install = [k for k, act in actions.items() if act == "install" and eng.registry.has(k)]
            if to_install:
                self.current_pkg = None
                self.store.update_job(self.job_id, {"phase": f"Установка ({len(to_install)} пак.)"})
                eng.install_packages(to_install)
                for p_name, st in list(self.pkg_statuses.items()):
                    if st in ("queued", "running"):
                        self.pkg_statuses[p_name] = "done"

            self.store.append_event(self.job_id, "🎉 План успешно выполнен.", level="success")
        except KeyboardInterrupt:
            final_status = "cancelled"
            err_msg = "Задача прервана оператором (выполнен откат транзакции)."
            if self.current_pkg:
                self.pkg_statuses[self.current_pkg] = "cancelled"
            self.store.append_event(self.job_id, f"❗ {err_msg}", pkg=self.current_pkg, level="warning")
        except Exception as exc:
            final_status = "failed"
            err_msg = str(exc)
            if self.current_pkg:
                self.pkg_statuses[self.current_pkg] = "failed"
            self.store.append_event(self.job_id, f"💥 Сбой выполнения плана: {err_msg}", pkg=self.current_pkg, level="error")
        finally:
            duration = round(time.monotonic() - started_ts, 2)
            self.store.update_job(self.job_id, {
                "status": final_status,
                "finished_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "duration_sec": duration,
                "phase": "Завершено" if final_status == "succeeded" else ("Отменено" if final_status == "cancelled" else "Ошибка"),
                "error": err_msg,
                "package_statuses": dict(self.pkg_statuses),
            })
            self.store.release_live_lock(self.job_id)

        return 0 if final_status == "succeeded" else 1


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    job_id = sys.argv[1]
    jobs_dir = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    roots = [sys.argv[3]] if len(sys.argv) > 3 and sys.argv[3] else None
    return JobWorker(job_id=job_id, jobs_dir=jobs_dir, search_roots=roots).run()


if __name__ == "__main__":
    raise SystemExit(main())
