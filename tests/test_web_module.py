"""
Тесты веб-модуля Deploy Engine (web/web.json, api.py, engine_bridge.py, env_service.py, job_store.py, job_worker.py):
- проверка контракта web.json v2 и нативного юнита web в manifest.json;
- проверка серверного ACL (admin vs operator live/sandbox, env.reveal);
- проверка get_state, preview_plan, inspect_env (--show), save_env_preset (#SKIP#/#GEN#);
- сквозной запуск фоновой задачи в Sandbox (JobWorker + polling + история) и отмена задачи.
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

DE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(DE_ROOT, "web")
if WEB_DIR not in sys.path:
    sys.path.insert(0, WEB_DIR)

from api import DeployEngineWebApi  # noqa: E402
from job_worker import JobWorker  # noqa: E402


class TestDeployEngineWebModule(unittest.TestCase):
    """Комплексная проверка бэкенда и фоновых задач веб-модуля Deploy Engine."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="de_web_mod_test_")
        self.repo_dir = os.path.join(self.tmp, "repo")
        self.jobs_dir = os.path.join(self.tmp, "jobs")
        self.sb_dir = os.path.join(self.tmp, "sandbox")
        self.env_dir = os.path.join(self.tmp, "env")
        self.backup_dir = os.path.join(self.tmp, "backup")
        self.cache_file = os.path.join(self.tmp, "packages.json")
        for path in (self.repo_dir, self.jobs_dir, self.sb_dir, self.env_dir, self.backup_dir):
            os.makedirs(path, exist_ok=True)
        self._orig_env = {
            k: os.environ.get(k) for k in ("DE_LOCAL_ENV_DIR", "DE_BACKUP_DIR", "DE_PACKAGES_CACHE")
        }
        os.environ["DE_LOCAL_ENV_DIR"] = self.env_dir
        os.environ["DE_BACKUP_DIR"] = self.backup_dir
        os.environ["DE_PACKAGES_CACHE"] = self.cache_file
        self._create_sample_package()
        self.api = DeployEngineWebApi(jobs_dir=self.jobs_dir, search_roots=[self.repo_dir])

    def tearDown(self):
        for k, val in self._orig_env.items():
            if val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = val
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_sample_package(self):
        pkg_dir = os.path.join(self.repo_dir, "demo-svc")
        os.makedirs(os.path.join(pkg_dir, "web"), exist_ok=True)
        os.makedirs(os.path.join(pkg_dir, "files"), exist_ok=True)
        with open(os.path.join(pkg_dir, "web", "web.json"), "w", encoding="utf-8") as fh:
            json.dump({"id": "demo-svc", "name": "Demo"}, fh)
        with open(os.path.join(pkg_dir, "web", "ui.js"), "w", encoding="utf-8") as fh:
            fh.write("export function mount() {}\n")
        with open(os.path.join(pkg_dir, "files", "app.py"), "w", encoding="utf-8") as fh:
            fh.write("print('ok')\n")
        with open(os.path.join(pkg_dir, "deploy.env"), "w", encoding="utf-8") as fh:
            fh.write(
                "# Настройки demo-svc\n"
                'APP_HOST="localhost"\n'
                'API_SECRET="{{PROMPT:Секретный ключ}}"\n'
                'AUTO_TOKEN="#GEN:hex:16#"\n'
            )
        with open(os.path.join(pkg_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({
                "name": "demo-svc",
                "version": "1.2.0",
                "desc": "Тестовый пакет для веб-модуля",
                "units": {
                    "deploy.env": {"type": "env"},
                    "files": {"type": "file"},
                    "web": {"type": "web"},
                },
            }, fh)

    def _ctx(self, action, payload=None, perms=None, role="admin"):
        return {
            "action": action,
            "payload": payload or {},
            "user": {
                "username": "tester",
                "role": role,
                "permissions": perms if perms is not None else ["*"],
            },
        }

    def test_web_json_and_manifest_web_unit(self):
        with open(os.path.join(WEB_DIR, "web.json"), encoding="utf-8") as fh:
            web_meta = json.load(fh)
        self.assertEqual(web_meta["schema_version"], 2)
        self.assertEqual(web_meta["id"], "deploy-engine")
        self.assertEqual(web_meta["backend"]["entry"], "api.py")
        self.assertEqual(web_meta["ui"]["entry"], "ui.js")
        self.assertIn("plan.execute", web_meta["acl"]["permissions"])
        self.assertIn("env.reveal", web_meta["acl"]["permissions"])

        with open(os.path.join(DE_ROOT, "manifest.json"), encoding="utf-8") as fh:
            mf = json.load(fh)
        self.assertIn("web", mf["packages"]["deploy-engine"]["include"])
        self.assertEqual(mf["units"]["web"]["type"], "web")

    def test_acl_blocks_operator_live_and_reveal(self):
        op_perms = ["view", "sandbox.run", "env.read", "logs.read"]
        live_res = self.api.handle(self._ctx("start_job", {
            "plan": {"actions": {"demo-svc": "install"}, "options": {"sandbox": False, "dry_run": False}},
        }, perms=op_perms, role="operator"))
        self.assertFalse(live_res["ok"])
        self.assertIn("plan.execute", live_res["error"])

        rev_res = self.api.handle(self._ctx("inspect_env", {
            "package": "demo-svc", "reveal": True, "sandbox": True, "sandbox_os": "debian",
        }, perms=op_perms, role="operator"))
        self.assertFalse(rev_res["ok"])
        self.assertIn("env.reveal", rev_res["error"])

    def test_state_preview_env_and_background_sandbox_job(self):
        st = self.api.handle(self._ctx("get_state", {"sandbox": True, "sandbox_os": "debian"}))
        self.assertTrue(st["ok"])
        self.assertEqual(st["data"]["engine_version"], "3.1.0")
        pkgs = {p["name"]: p for p in st["data"]["packages"]}
        self.assertIn("demo-svc", pkgs)
        self.assertTrue(pkgs["demo-svc"]["has_env"])

        plan = {
            "actions": {"demo-svc": "install"},
            "unit_updates": {},
            "backups": [],
            "restores": {},
            "options": {"sandbox": True, "sandbox_os": "debian", "sandbox_dir": self.sb_dir, "dry_run": False},
        }
        prev = self.api.handle(self._ctx("preview_plan", {"plan": plan}))
        self.assertTrue(prev["ok"])
        self.assertEqual(prev["data"]["ordered_packages"], ["demo-svc"])
        self.assertTrue(prev["data"]["requires_env_wizard"])

        # Сохранение пресета .env с #SKIP# удовлетворяет обязательный PROMPT
        save_res = self.api.handle(self._ctx("save_env_preset", {
            "package": "demo-svc",
            "values": {"APP_HOST": "web.local", "API_SECRET": "#SKIP#", "AUTO_TOKEN": "#GEN:hex:16#"},
            "sandbox": True,
            "sandbox_os": "debian",
        }))
        self.assertTrue(save_res["ok"], save_res)
        self.assertFalse(save_res["data"]["needs_confirmation"])

        # Инспектор .env (--show)
        insp = self.api.handle(self._ctx("inspect_env", {
            "package": "demo-svc", "preset": True, "sandbox": True, "sandbox_os": "debian",
        }))
        self.assertTrue(insp["ok"])
        self.assertEqual(insp["data"]["entries"]["API_SECRET"]["source"], "skip")

        # Запуск и выполнение воркера синхронно в тесте через JobStore + JobWorker
        job = self.api.job_store.create_job(
            plan=plan, ordered_packages=["demo-svc"], actor={"username": "admin", "role": "admin"}, mode="sandbox"
        )
        rc = JobWorker(job_id=job["job_id"], jobs_dir=self.jobs_dir, search_roots=[self.repo_dir]).run()
        self.assertEqual(rc, 0)

        status_res = self.api.handle(self._ctx("get_job_status", {"job_id": job["job_id"], "offset": 0}))
        self.assertTrue(status_res["ok"])
        self.assertEqual(status_res["data"]["job"]["status"], "succeeded")
        self.assertGreater(len(status_res["data"]["events"]), 0)

        hist = self.api.handle(self._ctx("list_jobs", {"limit": 10}))
        self.assertTrue(hist["ok"])
        self.assertEqual(hist["data"]["jobs"][0]["job_id"], job["job_id"])

        # Безопасная отмена завершённой задачи возвращает cancelled=False без ошибок
        cancel_res = self.api.handle(self._ctx("cancel_job", {"job_id": job["job_id"]}))
        self.assertTrue(cancel_res["ok"])
        self.assertFalse(cancel_res["data"]["cancelled"])

    def test_job_store_rejects_path_traversal(self):
        bad = self.api.handle(self._ctx("get_job_status", {"job_id": "../../etc/passwd"}))
        self.assertFalse(bad["ok"])
        self.assertIn("Некорректный идентификатор задачи", bad["error"])


if __name__ == "__main__":
    unittest.main()
