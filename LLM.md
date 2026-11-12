# 🤖 Deploy Engine 2.0 — Technical Context & Rules for LLM / AI

This file serves as a system prompt, technical architecture map, and development constitution for AI models (Claude, ChatGPT, Cursor, Gemini, etc.). When modifying code, adding features, or creating packages, strictly adhere to the constraints, directory layouts, and design principles documented below.

---

## 🏛️ Core Development Principles (Constitution)

1. **Strict 1 Class Per File Rule**:
   - Every `.py` file must contain **at most one class** (or dedicated utility functions if no class).
   - Never declare multiple domain classes or helper classes in the same file.
2. **Maximum 300 Lines Per File**:
   - No single file must ever exceed 300 lines of code.
   - If a file approaches 300 lines, it is an architectural signal to decompose responsibilities into smaller, focused single-responsibility classes.
3. **No God Objects / No Superclasses**:
   - The `Engine` class in `lib/core/engine.py` is strictly a lightweight facade (<250 lines) that coordinates specialized sub-managers.
   - Business logic must never be dumped directly into the engine.
4. **Terminal Directory Traversal (`DirectoryCrawler`)**:
   - When recursing through directory trees, if a directory contains `manifest.json`, the crawler records it as an autonomous package root and **terminates recursion for all subdirectories** of that folder.
5. **Package Cache (`packages.json`) & Instant Startup**:
   - Package discovery indexes are cached in `packages.json`.
   - On startup, the engine reads directly from `packages.json` without crawling disks unless `--rescan` or `deploy.py scan` is explicitly invoked.
6. **Namespace & Collision Disambiguation (`NameCollisionResolver`)**:
   - Packages can be addressed by short name (e.g. `api`) if unique across the repository.
   - If multiple packages share the same short name (e.g. `backend/api` vs `frontend/api`), the engine must raise `NameCollisionError` specifying all candidates and require full namespace.
7. **Persistent Dynamic Data Units (`data`)**:
   - Files of type `data` are routed to `/var/lib/de_{package_name}/` (mode `0o600` / `0o700`).
   - **Zero Overwrite Guarantee**: Existing databases and state files are **never overwritten** during reinstall or update.
   - On uninstall, data files are preserved by default (deleted only with `--purge`).
8. **Non-Destructive ENV Upsert (`EnvUpsertManager`)**:
   - When deploying updates to `/etc/default/de_{pkg}/{pkg}.env`, existing user-configured values and live secrets are **never modified or erased**.
   - Only newly introduced keys from the package template are appended.
   - Full reset to defaults is allowed only if `--clean-env` is explicitly passed.
   - On uninstall, environment directories are preserved by default (deleted only with `--purge`).
9. **Topological Dependency Graph (`DependencyGraph`)**:
   - Package inter-dependencies (`requires`) are resolved into an execution queue using Kahn's topological sort algorithm.
   - Cycles must be caught early with `DependencyCycleError`.
10. **Batched System Dependencies (`SystemPackageManager`)**:
    - `sys_packages` across all packages in the installation queue are deduplicated and installed in **a single batched call** to the OS package manager (`apt-get install -y ...`).
11. **Transactional Atomic Execution & LIFO Rollback (`TransactionManager`)**:
    - Every file creation, directory creation, symlink, and backup is recorded in a transaction journal.
    - If any step fails during installation or hooks, the engine executes an atomic rollback in reverse (LIFO) order, restoring backups and cleaning created files.
12. **Idempotence & Dry-Run Mode (`--dry-run` / `-n`)**:
    - All installation pipelines support simulation mode without touching the filesystem or invoking mutating OS commands.
13. **Local & Remote Inspection (`deploy.py list`)**:
    - Machine state recorded in `/etc/default/state.json` can be queried locally or over SSH via `--remote [user@]host[:port]` with human table or `--json` output.

---

## 📁 Repository Directory Map & Module Responsibilities

```text
deploy-engine/
├── manifest.json              # Package manifest for self-deployment into /opt/de_deploy-engine
├── deploy.env                 # System configuration template (/etc/default/de_deploy-engine/deploy-engine.env)
├── VERSION.txt                # Version number
├── COMMIT.txt                 # Commit descriptor (ignored in git)
├── CHANGELOG.txt              # Changelog history (ignored in git)
├── .gitignore                 # Git ignore rules
├── LICENSE                    # Open-source license
├── README.md                  # Comprehensive user documentation
├── LLM.md                     # AI Context, rules, and architecture specification (this file)
├── scripts/
│   ├── deploy-engine.sh       # System CLI launcher -> {{SYS_BIN}}/deploy-engine
│   └── deploy-ui.sh           # System TUI launcher -> {{SYS_BIN}}/deploy-ui
├── tests/
│   └── test_*.py              # Unit test suite covering all core features
└── files/
    ├── deploy.py              # CLI Entrypoint (install, uninstall, reinstall, backup, restore, list, info, scan)
    ├── deploy_ui.py           # TUI Bootstrapper (.venv auto-creation wrapper for Textual)
    ├── app.env.example        # Template for local standalone configuration (app.env)
    └── lib/
        ├── __init__.py
        ├── config.py          # Hierarchical config loader & dual-mode path resolver
        ├── engine.py          # Backward-compatible facade export (from lib.core.engine import Engine)
        ├── ui_app.py          # Textual TUI screen controller & action listeners
        ├── utils.py           # Root checking and GUI bootstrap helpers
    ├── core/                  # Core abstractions and facade
    │   ├── deploy_engine_error.py       # Base exception DeployEngineError
    │   ├── manifest_validation_error.py # Schema & manifest syntax errors
    │   ├── name_collision_error.py      # Namespace disambiguation error
    │   ├── dependency_cycle_error.py    # Cyclic dependency error
    │   ├── rollback_error.py            # Transaction rollback failure error
    │   ├── execution_context.py         # Runtime flags (dry_run, purge, clean_env, remote, json)
    │   └── engine.py                    # Lightweight orchestrator facade (<250 lines)
    ├── discovery/             # Package discovery and indexing
    │   ├── directory_crawler.py         # Terminal recursive crawler (stops at manifest.json)
    │   ├── manifest_parser.py           # JSON manifest parsing and schema normalization
    │   ├── name_collision_resolver.py   # Namespace & short name registry and resolver
    │   ├── package_cache_manager.py     # Atomic save/load of packages.json cache
    │   └── package_registry.py          # Central registry coordinating crawler, cache, and resolver
    ├── dependencies/          # Dependency managers
    │   ├── dependency_graph.py          # Kahn's topological sort and cycle detection
    │   ├── system_pkg_manager.py        # OS package manager detection & batched apt-get install
    │   ├── python_pkg_manager.py        # Pip and virtualenv requirements installer
    │   └── node_pkg_manager.py          # Npm package installer
    ├── installer/             # File and physical I/O pipelines
    │   ├── unit_path_resolver.py        # FHS destination route calculator and permission mapper
    │   ├── data_unit_installer.py       # Persistent data installer (/var/lib/de_{pkg}) with zero-overwrite
    │   ├── transaction_manager.py       # Action journal with LIFO rollback engine
    │   └── file_installer.py            # File copies, symlinks, directory creation, backups
    ├── env/                   # Environment & secrets management
    │   ├── env_parser.py                # Line-by-line .env parser preserving structure & comments
    │   ├── secret_masker.py             # Masking sensitive tokens/passwords in console output
    │   └── env_upsert_manager.py        # Non-destructive upsert, {{PROMPT}} resolver, --clean-env
    ├── lifecycle/             # Pre/Post lifecycle hooks
    │   ├── hook_context.py              # {{SYS_BIN}}, {{ENV_DIR}}, {{DATA_DIR}} macro interpolator
    │   └── hook_executor.py             # Shell hook runner with dry-run support
    ├── state/                 # State storage & query
    │   ├── state_repository.py          # Atomic /etc/default/state.json manager
    │   └── package_inspector.py         # List installed packages in table or JSON format
    ├── remote/                # SSH remote operations
    │   ├── ssh_client.py                # Subprocess-based SSH and SCP runner
    │   └── remote_deployer.py           # Tarball bundling, transport, and remote execution
    └── ui/                    # Textual GUI widgets
        ├── package_tree.py              # Spacebar-toggled package selection tree
        ├── plan_preview.py              # Deployment plan log preview
        └── styles.py                    # CSS styling rules
```

---

## 🧬 Unit Types & FHS Destination Conventions

The engine determines destination paths, permissions, and handling loops based on the declared `type`:

| Unit Type | Target FHS Path | Permissions | Behavior |
|:---|:---|:---|:---|
| `script` | `{{SYS_BIN}}/<name>` (`/usr/local/bin`) | `0o755` (`rwxr-xr-x`) | Executable system utilities |
| `unit` / `service` | `{{SYS_SYSTEMD}}/<name>` (`/etc/systemd/system`) | `0o644` (`rw-r--r--`) | Systemd daemon service units |
| `timer` | `{{SYS_SYSTEMD}}/<name>` (`/etc/systemd/system`) | `0o644` (`rw-r--r--`) | Systemd timer units |
| `env` | `{{ENV_PATH}}/de_{pkg}/{pkg}.env` (`/etc/default/...`) | `0o600` (`rw-------`) | Sandboxed secrets; non-destructive upsert |
| `data` | `{{STATE_DIR}}/de_{pkg}/<name>` (`/var/lib/...`) | `0o600` (dir `0o700`) | Persistent databases/state; **never overwritten** |
| `symlink` | `{{SYS_BIN}}/<link_name>` | `0o777` (`rwxrwxrwx`) | Symbolic link pointing to executable |
| `file` | Explicit `target` or `/etc/{pkg}/<name>` | `0o644` (`rw-r--r--`) | Configuration files or static assets |

---

## 📜 Manifest Specification (`manifest.json`)

Deploy Engine 2.0 supports both autonomous single-package manifests and multi-package inclusion manifests:

### Autonomous Package Manifest Example:
```json
{
  "name": "sample-daemon",
  "version": "1.2.0",
  "description": "Autonomous background service daemon",
  "requires": ["base-core"],
  "sys_packages": ["curl", "jq"],
  "python_packages": ["requirements.txt"],
  "units": {
    "deploy.env": {
      "type": "env",
      "desc": "Configuration and server tokens"
    },
    "sample-daemon.sh": {
      "type": "script",
      "desc": "CLI launcher"
    },
    "sample-daemon.service": {
      "type": "unit",
      "desc": "Systemd background service"
    },
    "registry.sqlite": {
      "type": "data",
      "desc": "Persistent registry database (never overwritten)"
    },
    "sample-cli": {
      "type": "symlink",
      "symlink": "{{SYS_BIN}}/sample-daemon.sh"
    }
  },
  "pre_install": "echo 'Preparing environment...'",
  "post_install": "systemctl daemon-reload && systemctl enable --now sample-daemon.service",
  "pre_uninstall": "systemctl stop sample-daemon.service || true",
  "post_uninstall": "systemctl daemon-reload"
}
```

---

## 🚨 Mandatory Rules for AI Agents Modifying the Codebase

1. **One Class Per File**: Never violate this rule. Create a new file in the appropriate subpackage under `lib/` for any new class.
2. **Length Guard**: Check file line count before finishing edits. Every file must remain under 300 lines.
3. **No Breaking Changes to Engine Facade**: `lib/engine.py` must continue to export `Engine` with backward compatibility for legacy callers and unit tests.
4. **Data Units Must Never Overwrite**: If modifying `DataUnitInstaller` or `FileInstaller`, never add code that forces overwriting existing destination files when `unit_type == "data"`.
5. **ENV Non-Destructive Invariant**: Existing variables in `/etc/default/de_{pkg}/{pkg}.env` must never be wiped or overwritten unless `clean_env=True` is explicitly specified by user flag.
6. **Transaction Cleanliness**: Always register created files, directories, symlinks, and backups with `TransactionManager` so automatic rollback succeeds if an error occurs.
