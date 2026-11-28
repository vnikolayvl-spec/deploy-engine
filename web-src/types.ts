// Типы данных веб-модуля Deploy Engine (de-web v2)

export type PackageAction = 'install' | 'reinstall' | 'uninstall';
export type SandboxOs = 'debian' | 'ubuntu' | 'alpine' | 'arch' | 'fedora' | 'macos';
export type FilterMode = 'all' | 'installed' | 'planned' | 'updates';
export type MainSection = 'orchestrator' | 'history';

export interface UnitSpec {
  name: string;
  type: string;
  dest: string;
  desc: string;
}

export interface BackupRecord {
  filename: string;
  timestamp: string;
  size_human: string;
  comment: string;
}

export interface PackageSummary {
  key: string;
  name: string;
  category: string;
  desc: string;
  installed: boolean;
  installed_version: string | null;
  available_version: string;
  update_status: 'current' | 'upgrade' | 'downgrade' | 'not_installed';
  compatible: boolean;
  platforms: string[];
  requires: string[];
  after: string[];
  manifest_available: boolean;
  is_external: boolean;
  has_env: boolean;
  has_preset: boolean;
  has_service: boolean;
  units: UnitSpec[];
  backups: BackupRecord[];
}

export interface EngineStateSnapshot {
  engine_version: string;
  distro: string;
  os_family: string;
  sandbox: boolean;
  sandbox_os: string;
  packages_dir: string;
  local_env_dir: string;
  active_job_id: string | null;
  categories: Record<string, string>;
  packages: PackageSummary[];
}

export interface PlanOptions {
  sandbox: boolean;
  sandbox_os: SandboxOs;
  dry_run: boolean;
  purge: boolean;
  clean_env: boolean;
  with_hooks: boolean;
  comment: string;
}

export interface PlanPayload {
  actions: Record<string, PackageAction>;
  unit_updates: Record<string, string[]>;
  backups: string[];
  restores: Record<string, string>;
  options: PlanOptions;
}

export interface PlanEnvCheck {
  package: string;
  unit: string;
  needs_confirmation: boolean;
  has_preset: boolean;
  dest: string;
}

export interface PlanPreviewData {
  ordered_packages: string[];
  auto_dependencies: string[];
  skipped_dependencies: string[];
  sys_packages: string[];
  env_checks: PlanEnvCheck[];
  requires_env_wizard: boolean;
  warnings: string[];
}

export interface PackageFileDetail {
  path: string;
  type: string;
  desc: string;
  exists: boolean;
}

export interface PackageDetailsData {
  package: string;
  namespace: string;
  installed: boolean;
  version: string;
  available_version: string;
  update_status: string;
  version_history: Array<{ version: string; installed_at?: number; timestamp?: string }>;
  installed_at: string;
  description: string;
  category: string;
  category_description: string;
  manifest_path: string;
  manifest_available: boolean;
  is_external_manifest: boolean;
  files_count: number;
  files: PackageFileDetail[];
}

export interface PackageLogsData {
  package: string;
  install_log: string;
  service_logs: string;
  has_service: boolean;
}

export interface EnvInspectEntry {
  raw: string;
  resolved: string;
  source: string;
  secret: boolean;
}

export interface EnvInspectReport {
  package: string;
  env_file: string;
  runtime_probe: boolean;
  warning: string | null;
  entries: Record<string, EnvInspectEntry>;
}

export interface EnvFormField {
  key: string;
  value: string;
  masked_preview: string;
  has_existing_value: boolean;
  default: string;
  prompt_label: string;
  required: boolean;
  comment: string;
  is_auto: boolean;
  is_gen: boolean;
  is_skip: boolean;
  is_secret: boolean;
}

export interface EnvFormData {
  package: string;
  unit?: string;
  has_env: boolean;
  preset_path?: string;
  system_path?: string;
  preset_exists: boolean;
  system_exists: boolean;
  needs_confirmation: boolean;
  fields: EnvFormField[];
}

export interface JobEvent {
  ts: string;
  pkg: string;
  level: 'info' | 'warning' | 'error' | 'success' | string;
  line: string;
}

export interface JobRecord {
  job_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | string;
  mode: 'live' | 'sandbox' | 'dry_run' | string;
  actor: { username: string; role: string };
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_sec: number;
  phase: string;
  error: string | null;
  ordered_packages: string[];
  package_statuses: Record<string, string>;
  plan?: PlanPayload;
  plan_summary?: Record<string, string>;
}
