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
* `file` (Default fallback type) ➔ `/opt/de_{package_name}/files/ / [relative_path]` (mode: `644`)

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
FILES=("/opt/de_sample-pkg/files/config.json")
```

### 5. Manifest Declarative Blueprint (`manifest.json` Specification)
When generating, validating, or parsing a package declaration, the engine and AI sub-routines must adhere to this dual-node JSON schema:
*   **The `"packages"` Node**: Contains logical meta-packages. It aggregates high-level human descriptions (`desc`), native OS requirements (`sys_packages`), installation inclusions (`include`), and sequential post-deployment execution commands (`post_install`).
*   **The `"units"` Node**: Contains the absolute definition for every resource declared in the `include` arrays. Each entity must specify an operational `type` and an optional explicit location override.

### 6. Declarative Unit Typings & Pipeline Execution Rules
The deployment pipeline (`file_installer.py`) modifies its execution loop, permission allocation, and I/O handlers based strictly on the declared unit `type`:
*   `type: "script"`: Automatically bound to `{{SYS_BIN}}` with executable permissions set to `0o755`.
*   `type: "unit"` / `type: "service"`: Bound to `{{SYS_SYSTEMD}}` with permissions set to `0o644`. Automatically queues `systemctl daemon-reload` and schedules `systemctl enable` hooks during orchestration.
*   `type: "file"`: **Recursive Multi-Target Processor**. Supports copying individual assets as well as whole directories. 
    *   *Special-File Isolation Rule*: The copying loop must utilize low-level file stat mask validation (`os.lstat().st_mode` paired with `stat.S_ISSOCK` and `stat.S_ISFIFO`). Any transient UNIX sockets (`.sock`) or named pipes (`FIFO`) found within source trees must be silently skipped to prevent I/O hanging and descriptor locks.
*   `type: "env"`: Triggers the 3-stage interactive secret compilation sequence. Reads templates via regular expressions, isolates inputs inside `/dev/tty` loops for TUI safety, merges live states to maintain persistence, and enforces highly restricted `0o600` permissions under `root:root` ownership.

### 7. Explicit Destination Precedence & Macro Expansion Token Rules
The path resolution layer executes two hard constraints before data hits the file system:
1.  **Explicit Target Override**: If a unit definition contains a `"dest"` attribute, the engine completely bypasses the default destination route conventions (FHS Fallbacks) and forces delivery to that exact absolute path.
2.  **Context Macro Expansion**: The following bracketed tokens must be dynamically expanded across all `src` and `dest` attributes prior to running installation blocks:
    *   `{{ROOT_DIR}}` — The global engine runtime directory.
    *   `{{BASE_DIR}}` — The absolute physical path of the directory hosting the active `manifest.json`.
    *   `{{SYS_BIN}}` — Standardized system binary folder pulled from `deploy_config.py`.
    *   `{{SYS_SYSTEMD}}` — Systemd service unit storage folder.

### 8. Gold-Master Reference Manifest Structure
When asked to output or generate an engine-compliant manifest, use this precise blueprint:
```json
{
  "packages": {
    "sample-service": {
      "desc": "Universal daemon meta-package with recursive codebases and templated environment injection",
      "sys_packages": [
        "python3",
        "python3-pip"
      ],
      "include": [
        "launcher.sh",
        "service.service",
        "production.env",
        "src_code"
      ],
      "post_install": [
        "systemctl daemon-reload",
        "systemctl enable service.service",
        "systemctl start service.service"
      ]
    }
  },
  "units": {
    "launcher.sh": {
      "type": "script",
      "desc": "Executable entrypoint wrapper script"
    },
    "service.service": {
      "type": "unit",
      "desc": "Systemd background daemon unit file"
    },
    "production.env": {
      "type": "env",
      "desc": "Interactive configuration template with token prompt markers",
      "dest": "/etc/default/de_sample/app.env"
    },
    "src_code": {
      "type": "file",
      "desc": "Core python package directory copied recursively with structural filtering",
      "dest": "/opt/de_sample/src_code"
    }
  }
}
```

---

## 🚨 Mandatory AI Code Modification Rules
1. **Never create a God Object**: Do not dump complex procedural operations into `lib/engine.py`. Keep it as an orchestrator proxy.
2. **Preserve Tabulation Integrity**: Textual applications are extremely layout-sensitive. Never miss matching spaces (4 for class fields, 8 for inner widget wrappers, 12-16 for context loops).
3. **No Brittle Auto-Restarts**: Never inject automated daemon-restarts into configuration file copiers. All lifecycle automation must remain explicitly declared inside `post_install` arrays.
4. **Maintain State Isolation**: Front-end widgets must fetch compilation items directly using proper references (e.g., `self.engine.files_to_deploy`), rather than cloning separate internal registries.

