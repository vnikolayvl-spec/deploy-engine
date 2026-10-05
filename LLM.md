# 🤖 Deploy Engine — Technical Context & Rules for LLM / AI

This file serves as a system prompt and technical architecture map for AI models (ChatGPT, Claude, Cursor, etc.). When modifying code or planning features, strictly adhere to the constraints, directory layouts, and design patterns documented below.

---

## 🛠️ Core Architectural Philosophy
1. **Decoupled State & Execution**: The `Engine` class acts strictly as a centralized data registry (State Hub). It must contain no recursive parsing loops or physical I/O execution logic.
2. **Pluggable Module Pattern**: All core tasks are delegated to single-responsibility service modules located in `lib/modules/`.
3. **Component-Based TUI**: UI layers use the `Textual` framework and must be separated into modular widgets located in `lib/ui/`.
4. **Linux Compliance (FHS)**: Built-in defaults mirror standard Linux hierarchy paths (FHS) and permission permissions.

---

## 📁 Repository Directory Map & Module Responsibilities

```text
deploy-engine/
├── deploy_config.py      # Global constants (SYS_BIN, SYS_SYSTEMD, ENV_PATH, ENV_PREFIX)
├── deploy.py             # CLI Entrypoint (install / uninstall / reinstall)
├── deploy_ui.py          # TUI Bootstrapper (.venv auto-creation wrapper)
└── lib/
    ├── engine.py         # Main orchestrator & context dispatcher (Clean Context Hub)
    ├── ui_app.py         # Screen controller widget mount point & button listeners
    ├── utils.py          # Shared tools (root check, .venv virtual env bootstrap)
    ├── modules/          # Core Back-End Plugins (Engine Context passed as `self`)
    │   ├── dependency_resolver.py # Recursively builds package resolution trees & handles 'requires'
    │   ├── env_manager.py         # Regular expression prompt parsers & 3-stage Upsert .env compiler
    │   ├── file_installer.py      # Core physical I/O pipeline: directories, shutil, and os.symlink
    │   ├── lifecycle_hooks.py     # Command string template expanding & shell runner wrappers
    │   ├── manifest_loader.py     # JSON reader, nested 'includes' crawler, and {{ROOT_DIR}} calculation
    │   ├── path_resolver.py       # 'files/' discovery loops & destination route calculator
    │   └── sys_packages.py        # Automated Linux package manager discovery (APT/YUM triggers)
    └── ui/               # Modular Front-End Components
        ├── styles.py              # Isolated global CSS code strings (APP_CSS layout grid)
        ├── package_tree.py        # Custom Tree widget with sequential Spacebar state loops
        └── plan_preview.py        # Real-time RichLog compiler for dependency mock updates
```

---

## 🧬 Concrete Data Models & State Loops

### 1. Unified Tree Spacebar Cycling Rules
When the user toggles a package node via the `Spacebar` in the TUI, states must transition linearly without mixing logical conditions:
* **For uninstalled packages** (Not listed in server registry): `none` ➔ `[+] install` ➔ `none`.
* **For deployed packages** (Marked green, found in `state.json`): `none` ➔ `[↻] reinstall` ➔ `[-] uninstall` ➔ `none`.
* **Cascade Loop**: Toggling a parent node must recursively push down the exact same status mapping to all child units and package dependents.

### 2. Destination Route Conventions (Path Resolver Mapping)
If a manifest unit omits a definitive `"dest"` attribute, route targets are computed implicitly using these strict fallbacks:
* `unit` / `service` / `timer` ➔ `config.SYS_SYSTEMD / [basename]` (mode: `644`)
* `script` / `.sh` / `.py` ➔ `config.SYS_BIN / [basename]` (mode: `755`)
* `env` ➔ `config.ENV_PATH / config.ENV_PREFIX{package_name} / [basename|env]` (mode: `600`)
* `file` (Default fallback type) ➔ `/etc/de_{package_name}/files/ / [relative_path]` (mode: `644`)

### 3. Three-Stage Secret Merging Sequence
When processing units with the `env` descriptor, compiled states must be merged linearly into the `dest` sandbox layout:
* **Layer 1**: Scan target asset path in `files/` inside the local repository. Extract core constants and catch text blocks containing `{{PROMPT:notice_text}}` using regular expressions.
* **Layer 2**: Mount existing `.env` fields already recorded inside the server path. Prevent overwriting old live secrets.
* **Layer 3**: Trigger user interactive prompts for uninitialized `{{PROMPT}}` values. Compile fields together and lock with permissions `600`.

### 4. Machine Metadata Assets (pack.env Scheme)
Every successful installation pipeline must dump an environment descriptor containing structured array collections into `config.ENV_PATH/config.ENV_PREFIX{package_name}/pack.env`:
```bash
SCRIPTS=("/usr/local/bin/sample.py")
TIMERS=()
UNITS=("/etc/systemd/system/sample.service")
FILES=("/etc/de_sample-pkg/files/config.json")
```

---

## 🚨 Mandatory AI Code Modification Rules
1. **Never create a God Object**: Do not dump complex procedural operations into `lib/engine.py`. Keep it as an orchestrator proxy.
2. **Preserve Tabulation Integrity**: Textual applications are extremely layout-sensitive. Never miss matching spaces (4 for class fields, 8 for inner widget wrappers, 12-16 for context loops).
3. **No Brittle Auto-Restarts**: Never inject automated daemon-restarts into configuration file copiers. All lifecycle automation must remain explicitly declared inside `post_install` arrays.
4. **Maintain State Isolation**: Front-end widgets must fetch compilation items directly using proper references (e.g., `self.engine.files_to_deploy`), rather than cloning separate internal registries.

