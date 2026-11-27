"""
Точечное транзакционное обновление отдельных юнитов пакета (Deploy Engine v3.0.0):
поддержка синтаксиса <pkg>:<unit>, флагов --only и --unit-type, проверка web.json для web-юнитов
и пропуск post_install хуков по умолчанию (если не передан --with-hooks).
"""
import os
from typing import Any, Dict, List, Optional, Tuple
from lib.config import DATA_PREFIX, ENV_PREFIX
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.version_utils import check_min_engine_version
from lib.providers.systemd_to_plist_converter import SystemdToPlistConverter


class SelectiveUnitRunner:
    """Точечное развертывание выбранных юнитов пакета с LIFO-откатом и контролем хуков."""

    @staticmethod
    def split_targets_and_units(
        targets: List[str],
        only_units: Optional[str] = None,
        unit_type: Optional[str] = None,
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Разбирает цели вида ['setup-notifier:web', 'setup-base'] и опции --only / --unit-type.
        Возвращает (список_полных_пакетов, карта {pkg_query: [unit_names]}).
        """
        cli_only = [u.strip() for u in (only_units or "").split(",") if u.strip()]
        full_pkgs: List[str] = []
        unit_map: Dict[str, List[str]] = {}

        for raw in targets:
            tok = str(raw or "").strip()
            if not tok:
                continue
            if ":" in tok:
                pkg_part, u_part = tok.split(":", 1)
                pkg_part, u_part = pkg_part.strip(), u_part.strip()
                if pkg_part and u_part:
                    unit_map.setdefault(pkg_part, [])
                    for item in u_part.split(","):
                        if item.strip() and item.strip() not in unit_map[pkg_part]:
                            unit_map[pkg_part].append(item.strip())
                    continue
            if cli_only or unit_type:
                unit_map.setdefault(tok, [])
                for item in cli_only:
                    if item not in unit_map[tok]:
                        unit_map[tok].append(item)
            else:
                full_pkgs.append(tok)

        return full_pkgs, unit_map

    @staticmethod
    def validate_web_unit(pkg_name: str, src_path: str, context) -> None:
        """Проверяет наличие web.json в директории юнита type='web' и пишет предупреждение при отсутствии."""
        if src_path and os.path.isdir(src_path):
            web_json = os.path.join(src_path, "web.json")
            if not os.path.isfile(web_json):
                context.log(
                    f"❗ Предупреждение: в web-юните пакета '{pkg_name}' ({src_path}) не найден web.json."
                )

    @classmethod
    def update_package_units(
        cls,
        engine,
        pkg_query: str,
        unit_names: Optional[List[str]] = None,
        unit_type_filter: Optional[str] = None,
        with_hooks: bool = False,
    ) -> bool:
        """Обновляет только указанные юниты пакета в рамках одной транзакции."""
        if not engine.registry.has(pkg_query):
            engine.context.log(engine.target_validator.format_missing_warning(pkg_query))
            return False

        pkg = engine.registry.get(pkg_query)
        if not engine.is_package_compatible(pkg):
            raise DeployEngineError(
                f"Пакет '{pkg['name']}' не поддерживает текущую систему ({engine.provider.distro_id})."
            )
        ok_ver, ver_err = check_min_engine_version(pkg)
        if not ok_ver:
            raise DeployEngineError(ver_err)

        canonical_name = pkg["name"]
        base_dir = os.path.abspath(pkg.get("base_dir", "."))
        pkg_units = pkg.get("units") or {}
        wanted_names = [u.strip() for u in (unit_names or []) if u.strip()]
        wanted_type = (unit_type_filter or "").strip().lower()

        selected: List[Tuple[str, Dict[str, Any], str, str, int, str]] = []
        for u_name, u_spec in pkg_units.items():
            src_p, dest_p, mode, u_type = engine.path_resolver.resolve(canonical_name, u_name, u_spec, base_dir)
            name_ok = (not wanted_names) or (u_name in wanted_names)
            type_ok = (not wanted_type) or (u_type.lower() == wanted_type)
            if name_ok and type_ok:
                selected.append((u_name, u_spec or {}, src_p, dest_p, mode, u_type))

        if not selected:
            criteria = ", ".join(wanted_names) if wanted_names else f"type={wanted_type}"
            raise DeployEngineError(
                f"В пакете '{canonical_name}' не найдено юнитов по фильтру ({criteria}). "
                f"Доступные юниты: {', '.join(sorted(pkg_units.keys())) or 'нет'}."
            )

        paths = engine.provider.get_paths()
        opt_pkg_dir = os.path.join(paths.get("opt_dir", "/opt"), f"de_{canonical_name}")
        env_pkg_dir = os.path.join(paths["env_path"], f"{ENV_PREFIX}{canonical_name}")
        data_pkg_dir = os.path.join(paths["state_dir"], f"{DATA_PREFIX}{canonical_name}")
        context_vars = {
            "{{ROOT_DIR}}": os.path.dirname(base_dir),
            "{{BASE_DIR}}": base_dir,
            "{{SYS_BIN}}": paths["sys_bin"],
            "{{SYS_SYSTEMD}}": paths["sys_systemd"],
            "{{ENV_PATH}}": paths["env_path"],
            "{{STATE_DIR}}": paths["state_dir"],
            "{{OPT_DIR}}": paths.get("opt_dir", "/opt"),
            "{{ENV_DIR}}": env_pkg_dir,
            "{{DATA_DIR}}": data_pkg_dir,
        }

        updated_files: List[str] = []
        static_env_vars: Dict[str, str] = {}
        service_units: Dict[str, tuple] = {}
        timer_units: Dict[str, tuple] = {}
        touched_systemd = False
        unit_labels = [item[0] for item in selected]

        try:
            with engine.context.package_operation_log(data_pkg_dir, canonical_name, f"update-units:{','.join(unit_labels)}"):
                engine.context.log(
                    f"\n🔧 Точечное обновление юнитов пакета {canonical_name}: {', '.join(unit_labels)}"
                )
                for u_name, u_spec, src_p, dest_p, mode, u_type in selected:
                    if u_type == "web":
                        cls.validate_web_unit(canonical_name, src_p, engine.context)
                    if u_type == "env":
                        engine.env_manager.upsert_env_file(src_p, dest_p, pkg_name=canonical_name)
                        static_env_vars.update(
                            SystemdToPlistConverter.parse_env_file(dest_p if os.path.isfile(dest_p) else src_p)
                        )
                        updated_files.append(dest_p)
                    elif engine.provider.uses_launchd_plist() and u_type in ("unit", "service", "timer"):
                        stem = SystemdToPlistConverter.get_service_stem(u_name)
                        target_map = timer_units if (u_type == "timer" or u_name.endswith(".timer")) else service_units
                        target_map[stem] = (u_name, src_p, dest_p, mode)
                    else:
                        symlink_target = (u_spec.get("symlink") or u_spec.get("src")) if u_type == "symlink" else None
                        if symlink_target:
                            for marker, real_val in context_vars.items():
                                symlink_target = str(symlink_target).replace(marker, real_val)
                        engine.file_installer.install_file(
                            src_p, dest_p, mode, u_type, symlink_target, context_vars=context_vars
                        )
                        updated_files.append(dest_p)
                        if u_type in ("unit", "service", "timer"):
                            touched_systemd = True

                if engine.provider.uses_launchd_plist() and (service_units or timer_units):
                    for p_path in engine.file_installer.install_launchd_plists(
                        canonical_name, service_units, timer_units, static_env_vars, context_vars
                    ):
                        updated_files.append(p_path)

                if touched_systemd and not engine.provider.uses_launchd_plist() and not engine.provider.is_sandbox:
                    engine.hook_executor.run_hook(
                        "daemon_reload", ["systemctl daemon-reload 2>/dev/null || true"], canonical_name, base_dir
                    )

                if with_hooks and pkg.get("post_install"):
                    engine.hook_executor.run_hook("post_install", pkg["post_install"], canonical_name, base_dir)
                elif pkg.get("post_install"):
                    engine.context.log("⏭ Хуки post_install пропущены (используйте --with-hooks для их запуска).")

                prev_state = engine.state_repo.get_installed_package(canonical_name) or {}
                merged_files = list(dict.fromkeys(list(prev_state.get("files") or []) + updated_files))
                mf_path = pkg.get("manifest_path") or os.path.join(base_dir, "manifest.json")
                engine.state_repo.mark_installed(
                    canonical_name,
                    pkg.get("version", prev_state.get("version", "1.0.0")),
                    merged_files,
                    pkg.get("namespace"),
                    desc=pkg.get("desc", ""),
                    manifest_path=mf_path,
                )
            engine.txn.commit()
            engine.context.log(f"✅ Юниты пакета '{canonical_name}' обновлены: {', '.join(unit_labels)}")
            return True
        except KeyboardInterrupt:
            engine._rollback_safely("\n❗ Обновление юнитов прервано пользователем (Ctrl+C).")
            raise
        except Exception as err:
            engine._rollback_safely(f"💥 Сбой при обновлении юнитов '{canonical_name}': {err}")
            raise DeployEngineError(f"Обновление юнитов прервано: {err}")
