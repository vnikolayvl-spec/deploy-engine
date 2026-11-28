// Главный фронтенд-плагин Deploy Engine v3.0.0 для панели de-web (Preact + DeModuleSdk)

import { h, render } from 'preact';
import { useCallback, useEffect, useMemo, useState } from 'preact/hooks';
import type { DeModuleSdk } from '../../web-sdk/types';
import { EnvWizardModal } from './components/EnvWizardModal';
import { JobHistoryTab } from './components/JobHistoryTab';
import { JobMonitorModal } from './components/JobMonitorModal';
import { PackageDetailsModal } from './components/PackageDetailsModal';
import { PackageTreePanel } from './components/PackageTreePanel';
import { MODULE_STYLES } from './styles';
import type {
  EngineStateSnapshot,
  FilterMode,
  JobRecord,
  MainSection,
  PackageAction,
  PackageSummary,
  PlanOptions,
  PlanPayload,
  PlanPreviewData,
  SandboxOs,
} from './types';

const EXPANDED_STORAGE_KEY = 'de_engine_web_expanded_v3';

const SANDBOX_OS_LIST: Array<{ value: SandboxOs; label: string }> = [
  { value: 'debian', label: 'Debian (apt / systemd)' },
  { value: 'ubuntu', label: 'Ubuntu (apt / systemd)' },
  { value: 'alpine', label: 'Alpine (apk)' },
  { value: 'arch', label: 'Arch Linux (pacman)' },
  { value: 'fedora', label: 'Fedora / RHEL (dnf)' },
  { value: 'macos', label: 'macOS (brew / launchd)' },
];

function loadExpandedSet(): Set<string> {
  try {
    const raw = sessionStorage.getItem(EXPANDED_STORAGE_KEY);
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) return new Set(arr.map(String));
    }
  } catch {
    // ignore storage failures
  }
  return new Set<string>();
}

function DeployEngineConsole({ sdk }: { sdk: DeModuleSdk }) {
  const [section, setSection] = useState<MainSection>('orchestrator');
  const [state, setState] = useState<EngineStateSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterMode>('all');
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(() => loadExpandedSet());
  const [selectedLeftPkg, setSelectedLeftPkg] = useState<string | null>(null);

  const [actions, setActions] = useState<Record<string, PackageAction>>({});
  const [unitUpdates, setUnitUpdates] = useState<Record<string, string[]>>({});
  const [backups, setBackups] = useState<string[]>([]);
  const [restores, setRestores] = useState<Record<string, string>>({});
  const [options, setOptions] = useState<PlanOptions>({
    sandbox: false,
    sandbox_os: 'debian',
    dry_run: false,
    purge: false,
    clean_env: false,
    with_hooks: false,
    comment: '',
  });

  const [preview, setPreview] = useState<PlanPreviewData | null>(null);
  const [detailsModal, setDetailsModal] = useState<{
    pkg: PackageSummary;
    tab: 'info' | 'env' | 'install_log' | 'service_logs';
  } | null>(null);
  const [envWizardPkgs, setEnvWizardPkgs] = useState<string[] | null>(null);
  const [monitorJobId, setMonitorJobId] = useState<string | null>(null);
  const [historyJobs, setHistoryJobs] = useState<JobRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const canExecuteLive = sdk.can('plan.execute');
  const canSandbox = sdk.can('sandbox.run') || canExecuteLive;
  const canRepoSync = sdk.can('repo.sync');
  const canLogs = sdk.can('logs.read');
  const canWriteEnv = sdk.can('env.write');

  // Подписка на смену темы de-web (токены --de-* обновляются автоматически на корне)
  useEffect(() => {
    const unsub = sdk.onThemeChange(() => {});
    return () => unsub();
  }, [sdk]);

  const fetchState = useCallback(async (sb: boolean, sbOs: SandboxOs, initExpand = false) => {
    setLoading(true);
    try {
      const snap = await sdk.api.call<EngineStateSnapshot>('get_state', {
        sandbox: sb,
        sandbox_os: sbOs,
      });
      setState(snap);
      if (initExpand) {
        setExpandedKeys((prev) => {
          if (prev.size > 0) return prev;
          const next = new Set<string>();
          for (const p of snap.packages) {
            next.add(`cat:${p.category || 'корень'}`);
          }
          try { sessionStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify(Array.from(next))); } catch {}
          return next;
        });
      }
    } catch (err: any) {
      sdk.notifyToast(`Не удалось загрузить состояние Deploy Engine: ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [sdk]);

  const fetchHistory = useCallback(async () => {
    if (!canLogs) return;
    setHistoryLoading(true);
    try {
      const res = await sdk.api.call<{ jobs: JobRecord[] }>('list_jobs', { limit: 50 });
      setHistoryJobs(res.jobs || []);
    } catch (err: any) {
      sdk.notifyToast(`Ошибка загрузки истории запусков: ${err.message}`, 'error');
    } finally {
      setHistoryLoading(false);
    }
  }, [sdk, canLogs]);

  useEffect(() => {
    fetchState(options.sandbox, options.sandbox_os, true);
  }, [options.sandbox, options.sandbox_os]);

  useEffect(() => {
    if (section === 'history') fetchHistory();
  }, [section, fetchHistory]);

  const planPayload: PlanPayload = useMemo(() => ({
    actions,
    unit_updates: unitUpdates,
    backups,
    restores,
    options,
  }), [actions, unitUpdates, backups, restores, options]);

  const hasAnyPlan = useMemo(() => {
    return (
      Object.keys(actions).length > 0 ||
      Object.values(unitUpdates).some((u) => u.length > 0) ||
      backups.length > 0 ||
      Object.keys(restores).length > 0
    );
  }, [actions, unitUpdates, backups, restores]);

  // Дебаунс-запрос серверного предпросмотра плана (порядок CLI + after + requires, зависимости, проверки .env)
  useEffect(() => {
    if (!hasAnyPlan) {
      setPreview(null);
      return;
    }
    const timer = setTimeout(() => {
      sdk.api.call<PlanPreviewData>('preview_plan', { plan: planPayload })
        .then(setPreview)
        .catch((err) => sdk.notifyToast(`Ошибка расчёта плана: ${err.message}`, 'error'));
    }, 150);
    return () => clearTimeout(timer);
  }, [planPayload, hasAnyPlan, sdk]);

  const toggleExpand = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      try { sessionStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify(Array.from(next))); } catch {}
      return next;
    });
  };

  const handleSetAction = (pkgKey: string, action: PackageAction | null) => {
    setActions((prev) => {
      const next = { ...prev };
      if (!action) delete next[pkgKey];
      else next[pkgKey] = action;
      return next;
    });
  };

  const handleToggleUnit = (pkgKey: string, unitName: string) => {
    setUnitUpdates((prev) => {
      const cur = new Set(prev[pkgKey] || []);
      if (cur.has(unitName)) cur.delete(unitName);
      else cur.add(unitName);
      const next = { ...prev };
      if (cur.size === 0) delete next[pkgKey];
      else next[pkgKey] = Array.from(cur);
      return next;
    });
  };

  const handleToggleBackup = (pkgName: string) => {
    setBackups((prev) => (prev.includes(pkgName) ? prev.filter((p) => p !== pkgName) : [...prev, pkgName]));
  };

  const handleSetRestore = (pkgName: string, selector: string) => {
    setRestores((prev) => {
      const next = { ...prev };
      if (!selector) delete next[pkgName];
      else next[pkgName] = selector;
      return next;
    });
  };

  const clearPlan = () => {
    setActions({});
    setUnitUpdates({});
    setBackups([]);
    setRestores({});
    setPreview(null);
  };

  const handleSyncPackages = async () => {
    setSyncing(true);
    try {
      const res = await sdk.api.call<{ packages_count: number; git_output: string }>('sync_packages', {});
      sdk.notifyToast(`Репозиторий обновлён · найдено пакетов: ${res.packages_count}`, 'success');
      await fetchState(options.sandbox, options.sandbox_os);
    } catch (err: any) {
      sdk.notifyToast(`Ошибка обновления пакетов: ${err.message}`, 'error');
    } finally {
      setSyncing(false);
    }
  };

  const launchJobNow = async () => {
    const isDestructive = !options.sandbox && !options.dry_run && (
      Object.values(actions).includes('uninstall') ||
      Object.keys(restores).length > 0 ||
      options.purge ||
      options.clean_env
    );
    if (isDestructive) {
      const ok = await sdk.requestConfirm({
        title: 'Подтвердите выполнение плана на сервере',
        message: 'План содержит удаление пакетов, восстановление из бэкапа или сброс данных/ENV. Продолжить?',
        confirmText: 'Выполнить план',
        danger: true,
      });
      if (!ok) return;
    }

    try {
      const res = await sdk.api.call<{ job_id: string }>('start_job', { plan: planPayload });
      sdk.notifyToast(`Задача ${res.job_id} запущена`, 'info');
      setMonitorJobId(res.job_id);
      await fetchState(options.sandbox, options.sandbox_os);
    } catch (err: any) {
      sdk.notifyToast(err.message || 'Не удалось запустить план', 'error');
    }
  };

  const handleRunPlanClick = async () => {
    if (!hasAnyPlan) return;
    if (!options.sandbox && !options.dry_run && !canExecuteLive) {
      sdk.notifyToast('Для боевого выполнения требуется право plan.execute (доступен Sandbox или Dry-Run)', 'warning');
      return;
    }
    try {
      const freshPreview = await sdk.api.call<PlanPreviewData>('preview_plan', { plan: planPayload });
      setPreview(freshPreview);
      if (freshPreview.warnings.length > 0) {
        sdk.notifyToast(freshPreview.warnings.join('; '), 'error');
        return;
      }
      if (freshPreview.requires_env_wizard && !options.dry_run) {
        const pending = freshPreview.env_checks.filter((e) => e.needs_confirmation).map((e) => e.package);
        setEnvWizardPkgs(pending);
        return;
      }
      await launchJobNow();
    } catch (err: any) {
      sdk.notifyToast(`Ошибка подготовки плана: ${err.message}`, 'error');
    }
  };

  // Левый список: пакеты с планом + транзитивные зависимости сверху, остальные установленные ниже
  const leftListItems = useMemo(() => {
    if (!state) return [];
    const autoDepSet = new Set(preview?.auto_dependencies || []);
    const byName = new Map(state.packages.map((p) => [p.name, p]));
    const plannedKeys = new Set<string>();
    for (const p of state.packages) {
      if (
        actions[p.key] ||
        (unitUpdates[p.key]?.length ?? 0) > 0 ||
        backups.includes(p.name) ||
        restores[p.name] ||
        autoDepSet.has(p.name)
      ) {
        plannedKeys.add(p.key);
      }
    }
    const items = state.packages.filter((p) => plannedKeys.has(p.key) || p.installed);
    items.sort((a, b) => {
      const ap = plannedKeys.has(a.key) ? 0 : 1;
      const bp = plannedKeys.has(b.key) ? 0 : 1;
      if (ap !== bp) return ap - bp;
      return a.name.localeCompare(b.name, 'ru');
    });
    return items.map((pkg) => ({
      pkg,
      isAutoDep: autoDepSet.has(pkg.name) && !actions[pkg.key],
      action: actions[pkg.key] || null,
      units: unitUpdates[pkg.key] || [],
      hasBackup: backups.includes(pkg.name),
      hasRestore: Boolean(restores[pkg.name]),
      refPkg: byName.get(pkg.name) || pkg,
    }));
  }, [state, preview, actions, unitUpdates, backups, restores]);

  const canLaunchCurrentMode = (options.sandbox || options.dry_run) ? canSandbox : canExecuteLive;

  return (
    <div class="de-eng-root">
      <style>{MODULE_STYLES}</style>

      {/* Верхняя панель управления модулем */}
      <div class="de-eng-topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          <div class="de-eng-seg" role="tablist">
            <button
              type="button"
              class={`de-eng-seg-btn ${section === 'orchestrator' ? 'active' : ''}`}
              onClick={() => setSection('orchestrator')}
            >
              Оркестратор
            </button>
            {canLogs && (
              <button
                type="button"
                class={`de-eng-seg-btn ${section === 'history' ? 'active' : ''}`}
                onClick={() => setSection('history')}
              >
                История и аудит
              </button>
            )}
          </div>
          {state && (
            <div class="de-eng-meta de-eng-mono">
              <span>Deploy Engine v{state.engine_version}</span>
              <span>·</span>
              <span>{state.sandbox ? `Sandbox: ${state.sandbox_os}` : `Хост: ${state.distro}`}</span>
            </div>
          )}
        </div>

        <div class="de-eng-actions">
          {canRepoSync && (
            <button type="button" class="de-eng-btn" disabled={syncing} onClick={handleSyncPackages}>
              {syncing ? 'Обновление...' : 'Обновить пакеты (git pull + scan)'}
            </button>
          )}
          <button
            type="button"
            class="de-eng-btn primary"
            disabled={!hasAnyPlan || !canLaunchCurrentMode || Boolean(state?.active_job_id && !options.sandbox && !options.dry_run)}
            onClick={handleRunPlanClick}
          >
            {options.dry_run ? 'Симулировать план' : options.sandbox ? 'Запустить в Sandbox' : 'Выполнить план'}
          </button>
        </div>
      </div>

      {/* Баннер активной фоновой задачи */}
      {state?.active_job_id && (
        <div class="de-eng-banner">
          <div>
            <strong>Выполняется фоновая задача:</strong>{' '}
            <span class="de-eng-mono">{state.active_job_id}</span>
          </div>
          <button type="button" class="de-eng-btn sm primary" onClick={() => setMonitorJobId(state.active_job_id)}>
            Открыть монитор и логи
          </button>
        </div>
      )}

      {section === 'history' ? (
        <JobHistoryTab
          jobs={historyJobs}
          loading={historyLoading}
          onRefresh={fetchHistory}
          onOpenJob={(id) => setMonitorJobId(id)}
        />
      ) : loading && !state ? (
        <div class="de-eng-panel" style={{ padding: '32px', textAlign: 'center', color: 'var(--de-muted)' }}>
          Сканирование реестра пакетов Deploy Engine...
        </div>
      ) : state ? (
        <div class="de-eng-workspace">
          {/* Левая колонка — список пакетов плана, зависимостей и установленных */}
          <div class="de-eng-panel">
            <div class="de-eng-panel-title">
              <span>Пакеты</span>
              <span class="de-eng-meta de-eng-mono">{leftListItems.length}</span>
            </div>
            <div class="de-eng-sidebar-list">
              <button
                type="button"
                class={`de-eng-sidebar-item ${selectedLeftPkg === null ? 'active' : ''}`}
                onClick={() => setSelectedLeftPkg(null)}
              >
                <span>Все пакеты плана</span>
                <span class="de-eng-mono" style={{ fontSize: '11px', color: 'var(--de-muted)' }}>
                  {preview?.ordered_packages.length || 0}
                </span>
              </button>
              {leftListItems.map(({ pkg, isAutoDep, action, units, hasBackup, hasRestore }) => {
                const tag = action === 'install'
                  ? '+'
                  : action === 'reinstall'
                    ? '↻'
                    : action === 'uninstall'
                      ? '−'
                      : isAutoDep
                        ? '+ деп'
                        : units.length > 0
                          ? `юниты:${units.length}`
                          : '✓';
                const tagCls = action === 'install' || isAutoDep
                  ? 'de-eng-status-ok'
                  : action === 'reinstall' || units.length > 0
                    ? 'de-eng-status-warn'
                    : action === 'uninstall'
                      ? 'de-eng-status-err'
                      : '';
                return (
                  <div key={pkg.key} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <button
                      type="button"
                      class={`de-eng-sidebar-item ${selectedLeftPkg === pkg.name ? 'active' : ''}`}
                      onClick={() => setSelectedLeftPkg(pkg.name)}
                      onDblClick={() => setDetailsModal({ pkg, tab: 'info' })}
                    >
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {pkg.name}
                        {hasBackup ? ' · бэкап' : ''}
                        {hasRestore ? ' · восст.' : ''}
                      </span>
                      <span class={`de-eng-mono ${tagCls}`} style={{ fontSize: '11px', flexShrink: 0 }}>
                        {tag}
                      </span>
                    </button>
                    <button
                      type="button"
                      class="de-eng-btn xs"
                      title="Открыть карточку пакета и логи"
                      onClick={() => setDetailsModal({ pkg, tab: 'info' })}
                    >
                      Инфо
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Центральная колонка — дерево пакетов + предпросмотр плана */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', minWidth: 0 }}>
            <PackageTreePanel
              packages={state.packages}
              categories={state.categories}
              search={search}
              onSearchChange={setSearch}
              filter={filter}
              onFilterChange={setFilter}
              expandedKeys={expandedKeys}
              onToggleExpand={toggleExpand}
              actions={actions}
              unitUpdates={unitUpdates}
              backups={backups}
              restores={restores}
              onSetAction={handleSetAction}
              onToggleUnit={handleToggleUnit}
              onToggleBackup={handleToggleBackup}
              onSetRestore={handleSetRestore}
              onOpenDetails={(pkg, tab = 'info') => setDetailsModal({ pkg, tab })}
              canWriteEnv={canWriteEnv}
            />

            <div class="de-eng-panel">
              <div class="de-eng-panel-title">
                <span>Предпросмотр плана{selectedLeftPkg ? `: ${selectedLeftPkg}` : ''}</span>
                {hasAnyPlan && (
                  <button type="button" class="de-eng-btn xs" onClick={clearPlan}>
                    Очистить план
                  </button>
                )}
              </div>

              {!hasAnyPlan ? (
                <div style={{ color: 'var(--de-muted)', fontSize: '12px' }}>
                  Выберите пакеты, отдельные юниты или операции резервного копирования в дереве выше.
                </div>
              ) : !preview ? (
                <div style={{ color: 'var(--de-muted)', fontSize: '12px' }}>Расчёт порядка установки и зависимостей...</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
                  {preview.warnings.length > 0 && (
                    <div class="de-eng-status-err">
                      Ошибки плана: {preview.warnings.join(' · ')}
                    </div>
                  )}
                  <div>
                    <span style={{ color: 'var(--de-muted)' }}>Порядок выполнения: </span>
                    <span class="de-eng-mono" style={{ fontWeight: 600 }}>
                      {preview.ordered_packages.join(' → ') || '—'}
                    </span>
                  </div>
                  {preview.auto_dependencies.length > 0 && (
                    <div>
                      <span style={{ color: 'var(--de-muted)' }}>Подтянутые зависимости: </span>
                      <span class="de-eng-mono de-eng-status-accent">{preview.auto_dependencies.join(', ')}</span>
                    </div>
                  )}
                  {preview.skipped_dependencies.length > 0 && (
                    <div>
                      <span style={{ color: 'var(--de-muted)' }}>Уже установлены (пропуск): </span>
                      <span class="de-eng-mono">{preview.skipped_dependencies.join(', ')}</span>
                    </div>
                  )}
                  {preview.sys_packages.length > 0 && (
                    <div>
                      <span style={{ color: 'var(--de-muted)' }}>Системные пакеты ({preview.sys_packages.length}): </span>
                      <span class="de-eng-mono">{preview.sys_packages.join(', ')}</span>
                    </div>
                  )}
                  {preview.env_checks.length > 0 && (
                    <div>
                      <span style={{ color: 'var(--de-muted)' }}>Конфигурации .env: </span>
                      {preview.env_checks.map((ec, i) => (
                        <span key={ec.package} class="de-eng-mono">
                          {i > 0 ? ' · ' : ''}
                          {ec.package}{' '}
                          <span class={ec.needs_confirmation ? 'de-eng-status-warn' : 'de-eng-status-ok'}>
                            ({ec.needs_confirmation ? 'требует подтверждения' : 'готов'})
                          </span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Правая колонка — настройки Sandbox / Dry-Run / флаги и запуск */}
          <div class="de-eng-panel">
            <div class="de-eng-panel-title">Параметры запуска</div>

            <label class="de-eng-check-row">
              <input
                type="checkbox"
                checked={options.sandbox}
                onChange={(e) => {
                  const sb = (e.target as HTMLInputElement).checked;
                  clearPlan();
                  setOptions((o) => ({ ...o, sandbox: sb }));
                }}
              />
              <span>Sandbox (песочница)</span>
            </label>

            {options.sandbox && (
              <div>
                <div style={{ fontSize: '12px', color: 'var(--de-muted)', marginBottom: '4px' }}>
                  Целевая ОС песочницы
                </div>
                <select
                  class="de-eng-select"
                  value={options.sandbox_os}
                  onChange={(e) => {
                    const osVal = (e.target as HTMLSelectElement).value as SandboxOs;
                    clearPlan();
                    setOptions((o) => ({ ...o, sandbox_os: osVal }));
                  }}
                >
                  {SANDBOX_OS_LIST.map((item) => (
                    <option key={item.value} value={item.value}>{item.label}</option>
                  ))}
                </select>
              </div>
            )}

            <label class="de-eng-check-row">
              <input
                type="checkbox"
                checked={options.dry_run}
                onChange={(e) => setOptions((o) => ({ ...o, dry_run: (e.target as HTMLInputElement).checked }))}
              />
              <span>Dry-Run (симуляция без записи)</span>
            </label>

            <label class="de-eng-check-row">
              <input
                type="checkbox"
                checked={options.with_hooks}
                onChange={(e) => setOptions((o) => ({ ...o, with_hooks: (e.target as HTMLInputElement).checked }))}
              />
              <span>Выполнять post_install при обновлении юнитов</span>
            </label>

            <label class="de-eng-check-row">
              <input
                type="checkbox"
                checked={options.purge}
                onChange={(e) => setOptions((o) => ({ ...o, purge: (e.target as HTMLInputElement).checked }))}
              />
              <span>Удалять data и .env (--purge)</span>
            </label>

            <label class="de-eng-check-row">
              <input
                type="checkbox"
                checked={options.clean_env}
                onChange={(e) => setOptions((o) => ({ ...o, clean_env: (e.target as HTMLInputElement).checked }))}
              />
              <span>Сбросить .env к шаблону (--clean-env)</span>
            </label>

            <div>
              <div style={{ fontSize: '12px', color: 'var(--de-muted)', marginBottom: '4px' }}>
                Комментарий к бэкапу / запуску
              </div>
              <input
                type="text"
                class="de-eng-input"
                placeholder="Например: перед обновлением веб-модулей"
                value={options.comment}
                onInput={(e) => setOptions((o) => ({ ...o, comment: (e.target as HTMLInputElement).value }))}
              />
            </div>

            <div class="de-eng-meta de-eng-mono" style={{ borderTop: '1px solid var(--de-border)', paddingTop: '10px' }}>
              <span>Пресеты: {state.local_env_dir}</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button
                type="button"
                class="de-eng-btn primary"
                style={{ width: '100%' }}
                disabled={!hasAnyPlan || !canLaunchCurrentMode}
                onClick={handleRunPlanClick}
              >
                {options.dry_run ? 'Симулировать план' : options.sandbox ? 'Запустить в Sandbox' : 'Выполнить план'}
              </button>
              {hasAnyPlan && (
                <button type="button" class="de-eng-btn" style={{ width: '100%' }} onClick={clearPlan}>
                  Сбросить выбор
                </button>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {/* Модальное окно карточки пакета */}
      {detailsModal && (
        <PackageDetailsModal
          sdk={sdk}
          pkg={detailsModal.pkg}
          initialTab={detailsModal.tab}
          sandbox={options.sandbox}
          sandboxOs={options.sandbox_os}
          onClose={() => setDetailsModal(null)}
          onEnvSaved={() => fetchState(options.sandbox, options.sandbox_os)}
        />
      )}

      {/* Мастер обязательного подтверждения .env */}
      {envWizardPkgs && (
        <EnvWizardModal
          sdk={sdk}
          pendingPackages={envWizardPkgs}
          sandbox={options.sandbox}
          sandboxOs={options.sandbox_os}
          onCancel={() => setEnvWizardPkgs(null)}
          onAllConfirmed={() => {
            setEnvWizardPkgs(null);
            launchJobNow();
          }}
        />
      )}

      {/* Монитор выполнения фоновой задачи / просмотр лога истории */}
      {monitorJobId && (
        <JobMonitorModal
          sdk={sdk}
          jobId={monitorJobId}
          onClose={() => setMonitorJobId(null)}
          onFinished={() => {
            clearPlan();
            fetchState(options.sandbox, options.sandbox_os);
            if (section === 'history') fetchHistory();
          }}
        />
      )}
    </div>
  );
}

export function mount(container: HTMLElement, sdk: DeModuleSdk): () => void {
  render(h(DeployEngineConsole, { sdk }), container);
  return () => {
    render(null, container);
  };
}
