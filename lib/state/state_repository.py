"""
State repository managing /etc/default/state.json.
"""
import json
import os
import time
from typing import Any, Dict, List, Optional
from deploy_config import ENV_PATH
from lib.core.execution_context import ExecutionContext


class StateRepository:
    """Хранилище состояния установленных пакетов в /etc/default/state.json."""

    def __init__(self, state_file_path: Optional[str] = None, context: Optional[ExecutionContext] = None):
        self.state_file_path = state_file_path or os.path.join(ENV_PATH, "state.json")
        self.context = context or ExecutionContext()

    def get_state(self) -> Dict[str, Any]:
        """Возвращает текущее состояние."""
        if not os.path.exists(self.state_file_path):
            return {"installed": {}}
        try:
            with open(self.state_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "installed" in data:
                    return data
                return {"installed": {}}
        except Exception:
            return {"installed": {}}

    def save_state(self, state_data: Dict[str, Any]) -> bool:
        """Сохраняет состояние атомарно."""
        if self.context.dry_run:
            self.context.log(f"🔎 [DRY-RUN] Обновление состояния в {self.state_file_path}")
            return True

        state_dir = os.path.dirname(self.state_file_path)
        os.makedirs(state_dir, exist_ok=True)

        tmp_path = f"{self.state_file_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.state_file_path)
            os.chmod(self.state_file_path, 0o644)
            return True
        except Exception as err:
            self.context.log(f"⚠️ Не удалось сохранить состояние в {self.state_file_path}: {err}")
            return False

    def mark_installed(
        self,
        pkg_name: str,
        version: str,
        files: List[str],
        namespace: Optional[str] = None,
    ) -> None:
        """Регистрирует пакет как установленный."""
        state = self.get_state()
        state["installed"][pkg_name] = {
            "version": version,
            "installed_at": time.time(),
            "files": files,
            "namespace": namespace or pkg_name,
        }
        self.save_state(state)

    def mark_uninstalled(self, pkg_name: str) -> None:
        """Удаляет запись о пакете из состояния."""
        state = self.get_state()
        if pkg_name in state.get("installed", {}):
            del state["installed"][pkg_name]
            self.save_state(state)

    def get_installed_package(self, pkg_name: str) -> Optional[Dict[str, Any]]:
        """Возвращает метаданные установленного пакета."""
        state = self.get_state()
        return state.get("installed", {}).get(pkg_name)
