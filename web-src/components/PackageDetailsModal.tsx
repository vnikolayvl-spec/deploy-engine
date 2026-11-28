// Модальная карточка пакета: Информация, Конфигурация (.env --show + редактор), Лог установки, Логи службы

import { h } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import type { DeModuleSdk } from '../../../web-sdk/types';
import type {
  EnvFormData,
  EnvInspectReport,
  PackageDetailsData,
  PackageLogsData,
  PackageSummary,
  SandboxOs,
} from '../types';

type DetailTab = 'info' | 'env' | 'install_log' | 'service_logs';

interface Props {
  sdk: DeModuleSdk;
  pkg: PackageSummary;
  initialTab: DetailTab;
  sandbox: boolean;
  sandboxOs: SandboxOs;
  onClose: () => void;
  onEnvSaved: () => void;
}

export function PackageDetailsModal(props: Props) {
  const { sdk, pkg, initialTab, sandbox, sandboxOs, onClose, onEnvSaved } = props;
  const [tab, setTab] = useState<DetailTab>(initialTab);
  const [details, setDetails] = useState<PackageDetailsData | null>(null);
  const [logs, setLogs] = useState<PackageLogsData | null>(null);
  const [envSubTab, setEnvSubTab] = useState<'inspect' | 'edit'>('inspect');
  const [inspectReport, setInspectReport] = useState<EnvInspectReport | null>(null);
  const [revealSecrets, setRevealSecrets] = useState(false);
  const [envForm, setEnvForm] = useState<EnvFormData | null>(null);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [restarting, setRestarting] = useState(false);

  const canReadEnv = sdk.can('env.read');
  const canWriteEnv = sdk.can('env.write');
  const canRevealEnv = sdk.can('env.reveal');
  const canLogs = sdk.can('logs.read');
  const canService = sdk.can('service.control');
  const canExecute = sdk.can('plan.execute');

  useEffect(() => {
    let active = true;
    setBusy(true);
    sdk.api.call<PackageDetailsData>('get_package_details', {
      package: pkg.key, sandbox, sandbox_os: sandboxOs,
    }).then((res) => {
      if (active) setDetails(res);
    }).catch((err) => {
      if (active) sdk.notifyToast(`Ошибка загрузки карточки: ${err.message}`, 'error');
    }).finally(() => {
      if (active) setBusy(false);
    });
    return () => { active = false; };
  }, [pkg.key, sandbox, sandboxOs]);

  useEffect(() => {
    if ((tab === 'install_log' || tab === 'service_logs') && canLogs && !logs) {
      sdk.api.call<PackageLogsData>('get_package_logs', {
        package: pkg.key, sandbox, sandbox_os: sandboxOs,
      }).then(setLogs).catch((err) => sdk.notifyToast(`Ошибка чтения логов: ${err.message}`, 'error'));
    }
  }, [tab, canLogs]);

  const loadEnvInspect = async (revealFlag: boolean) => {
    if (!canReadEnv) return;
    try {
      const rep = await sdk.api.call<EnvInspectReport>('inspect_env', {
        package: pkg.key, reveal: revealFlag, sandbox, sandbox_os: sandboxOs,
      });
      setInspectReport(rep);
    } catch (err: any) {
      sdk.notifyToast(`Не удалось загрузить .env (--show): ${err.message}`, 'error');
    }
  };

  const loadEnvForm = async () => {
    if (!canReadEnv) return;
    try {
      const form = await sdk.api.call<EnvFormData>('get_env_form', {
        package: pkg.key, reveal: false, sandbox, sandbox_os: sandboxOs,
      });
      setEnvForm(form);
      const init: Record<string, string> = {};
      for (const f of form.fields) {
        init[f.key] = f.value;
      }
      setDraftValues(init);
    } catch (err: any) {
      sdk.notifyToast(`Не удалось загрузить форму .env: ${err.message}`, 'error');
    }
  };

  useEffect(() => {
    if (tab === 'env' && canReadEnv) {
      loadEnvInspect(revealSecrets);
      loadEnvForm();
    }
  }, [tab, revealSecrets]);

  const handleSaveEnv = async (applySystem: boolean) => {
    if (applySystem && !sandbox) {
      const ok = await sdk.requestConfirm({
        title: 'Применить .env в систему?',
        message: `Новые значения будут записаны в системный файл .env пакета «${pkg.name}» с сохранением существующих комментариев.`,
        confirmText: 'Сохранить и применить',
      });
      if (!ok) return;
    }
    setBusy(true);
    try {
      await sdk.api.call('save_env_preset', {
        package: pkg.key,
        values: draftValues,
        apply_system: applySystem,
        sandbox,
        sandbox_os: sandboxOs,
      });
      sdk.notifyToast(applySystem ? 'Пресет сохранён и применён в системный .env' : 'Пресет .env сохранён', 'success');
      onEnvSaved();
      await loadEnvInspect(revealSecrets);
      await loadEnvForm();
    } catch (err: any) {
      sdk.notifyToast(err.message || 'Ошибка сохранения .env', 'error');
    } finally {
      setBusy(false);
    }
  };

  const handleRestartService = async () => {
    const ok = await sdk.requestConfirm({
      title: `Перезапустить службу ${pkg.name}?`,
      message: 'Службы systemd/launchd выбранного пакета будут перезапущены.',
      confirmText: 'Перезапустить',
      danger: true,
    });
    if (!ok) return;
    setRestarting(true);
    try {
      const res = await sdk.api.call<{ output: string }>('restart_service', {
        package: pkg.key, sandbox, sandbox_os: sandboxOs,
      });
      sdk.notifyToast(res.output || 'Служба перезапущена', 'success');
      if (canLogs) {
        const fresh = await sdk.api.call<PackageLogsData>('get_package_logs', {
          package: pkg.key, sandbox, sandbox_os: sandboxOs,
        });
        setLogs(fresh);
      }
    } catch (err: any) {
      sdk.notifyToast(`Ошибка перезапуска: ${err.message}`, 'error');
    } finally {
      setRestarting(false);
    }
  };

  return (
    <div class="de-eng-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div class="de-eng-modal" role="dialog" aria-modal="true" aria-label={`Карточка пакета ${pkg.name}`}>
        <div class="de-eng-modal-hdr">
          <div>
            <div style={{ fontFamily: 'var(--de-font-display)', fontSize: '16px', fontWeight: 700 }}>
              {pkg.name}
            </div>
            <div class="de-eng-meta de-eng-mono">
              <span>{pkg.category}</span>
              <span>·</span>
              <span>v{pkg.installed ? pkg.installed_version : pkg.available_version}</span>
              {pkg.installed && pkg.update_status === 'upgrade' && (
                <span class="de-eng-status-warn">· Доступна v{pkg.available_version}</span>
              )}
            </div>
          </div>
          <div class="de-eng-actions">
            {pkg.has_service && canService && (
              <button type="button" class="de-eng-btn sm" disabled={restarting} onClick={handleRestartService}>
                {restarting ? 'Перезапуск...' : 'Перезапустить службу'}
              </button>
            )}
            <button type="button" class="de-eng-btn sm" onClick={onClose}>Закрыть</button>
          </div>
        </div>

        <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--de-border)', background: 'var(--de-surface)' }}>
          <div class="de-eng-seg">
            <button type="button" class={`de-eng-seg-btn ${tab === 'info' ? 'active' : ''}`} onClick={() => setTab('info')}>
              Информация
            </button>
            {canReadEnv && (
              <button type="button" class={`de-eng-seg-btn ${tab === 'env' ? 'active' : ''}`} onClick={() => setTab('env')}>
                Конфигурация (.env)
              </button>
            )}
            {canLogs && (
              <button type="button" class={`de-eng-seg-btn ${tab === 'install_log' ? 'active' : ''}`} onClick={() => setTab('install_log')}>
                Лог установки
              </button>
            )}
            {canLogs && (
              <button type="button" class={`de-eng-seg-btn ${tab === 'service_logs' ? 'active' : ''}`} onClick={() => setTab('service_logs')}>
                Логи службы
              </button>
            )}
          </div>
        </div>

        <div class="de-eng-modal-body">
          {tab === 'info' && (
            busy && !details ? (
              <div style={{ color: 'var(--de-muted)' }}>Загрузка информации о пакете...</div>
            ) : details ? (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '12px' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--de-muted)' }}>Статус</div>
                    <div class={details.installed ? 'de-eng-status-ok' : ''}>
                      {details.installed ? 'Установлен' : 'Не установлен'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--de-muted)' }}>Версия</div>
                    <div class="de-eng-mono">
                      v{details.version}
                      {details.installed && details.update_status === 'upgrade' ? ` → v${details.available_version}` : ''}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--de-muted)' }}>Дата установки</div>
                    <div class="de-eng-mono">{details.installed_at}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--de-muted)' }}>Категория</div>
                    <div>{details.category || 'корень'}</div>
                  </div>
                </div>
                {details.description && (
                  <div style={{ color: 'var(--de-text-secondary)' }}>{details.description}</div>
                )}
                {details.version_history && details.version_history.length > 0 && (
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: '6px' }}>История версий</div>
                    <div class="de-eng-meta de-eng-mono">
                      {details.version_history.map((hItem, idx) => (
                        <span key={idx}>
                          {idx > 0 ? ' · ' : ''}v{hItem.version} ({hItem.timestamp || '—'})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <div style={{ fontWeight: 600, marginBottom: '6px' }}>
                    Системные пути ({details.files_count})
                  </div>
                  <table class="de-eng-table">
                    <thead>
                      <tr>
                        <th>Диск</th>
                        <th>Тип</th>
                        <th>Путь</th>
                        <th>Описание</th>
                      </tr>
                    </thead>
                    <tbody>
                      {details.files.map((f) => (
                        <tr key={f.path}>
                          <td class={f.exists ? 'de-eng-status-ok' : 'de-eng-status-warn'}>
                            {f.exists ? 'Есть' : 'Нет'}
                          </td>
                          <td class="de-eng-mono">{f.type}</td>
                          <td class="de-eng-mono">{f.path}</td>
                          <td style={{ color: 'var(--de-muted)' }}>{f.desc || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--de-muted)' }}>Данные о пакете недоступны.</div>
            )
          )}

          {tab === 'env' && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap' }}>
                <div class="de-eng-seg">
                  <button
                    type="button"
                    class={`de-eng-seg-btn ${envSubTab === 'inspect' ? 'active' : ''}`}
                    onClick={() => setEnvSubTab('inspect')}
                  >
                    Развернутые значения (--show)
                  </button>
                  <button
                    type="button"
                    class={`de-eng-seg-btn ${envSubTab === 'edit' ? 'active' : ''}`}
                    onClick={() => setEnvSubTab('edit')}
                  >
                    Редактор пресета
                  </button>
                </div>
                {envSubTab === 'inspect' && canRevealEnv && (
                  <button
                    type="button"
                    class="de-eng-btn sm"
                    onClick={() => setRevealSecrets((v) => !v)}
                  >
                    {revealSecrets ? 'Скрыть секреты' : 'Показать секреты (--reveal)'}
                  </button>
                )}
              </div>

              {envSubTab === 'inspect' ? (
                inspectReport ? (
                  <>
                    <div class="de-eng-meta de-eng-mono">
                      <span>Файл: {inspectReport.env_file || '(не создан)'}</span>
                      {inspectReport.warning && <span>· {inspectReport.warning}</span>}
                    </div>
                    <table class="de-eng-table">
                      <thead>
                        <tr>
                          <th>Ключ</th>
                          <th>В .env</th>
                          <th>Актуальное значение</th>
                          <th>Источник</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(inspectReport.entries).map(([k, item]) => (
                          <tr key={k}>
                            <td class="de-eng-mono" style={{ fontWeight: 600 }}>{k}</td>
                            <td class="de-eng-mono" style={{ color: 'var(--de-muted)' }}>{item.raw || '""'}</td>
                            <td class="de-eng-mono">{item.resolved || '""'}</td>
                            <td class="de-eng-mono">{item.source}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                ) : (
                  <div style={{ color: 'var(--de-muted)' }}>Загрузка развернутой конфигурации...</div>
                )
              ) : (
                envForm && envForm.has_env ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div class="de-eng-meta de-eng-mono">
                      <span>Пресет: {envForm.preset_path}</span>
                      <span>·</span>
                      <span>{envForm.preset_exists ? 'Сохранён' : 'Ещё не создан'}</span>
                    </div>
                    {envForm.fields.map((f) => (
                      <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingBottom: '10px', borderBottom: '1px solid var(--de-border)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                          <label class="de-eng-mono" style={{ fontWeight: 600 }}>
                            {f.key}
                            {f.required && <span class="de-eng-status-err" style={{ marginLeft: '6px' }}>Обязательно</span>}
                            {f.is_secret && <span style={{ marginLeft: '6px', color: 'var(--de-muted)', fontWeight: 400 }}>· секрет</span>}
                          </label>
                          {canWriteEnv && (
                            <div class="de-eng-actions">
                              <button type="button" class="de-eng-btn xs" onClick={() => setDraftValues((d) => ({ ...d, [f.key]: '#AUTO#' }))}>#AUTO#</button>
                              <button type="button" class="de-eng-btn xs" onClick={() => setDraftValues((d) => ({ ...d, [f.key]: '#GEN#' }))}>#GEN#</button>
                              <button type="button" class="de-eng-btn xs" onClick={() => setDraftValues((d) => ({ ...d, [f.key]: '#SKIP#' }))}>#SKIP#</button>
                            </div>
                          )}
                        </div>
                        {(f.prompt_label || f.comment) && (
                          <div style={{ fontSize: '12px', color: 'var(--de-muted)' }}>
                            {f.prompt_label || f.comment}
                          </div>
                        )}
                        <input
                          type={f.is_secret ? 'password' : 'text'}
                          class="de-eng-input de-eng-mono"
                          disabled={!canWriteEnv}
                          placeholder={f.is_secret && f.has_existing_value ? `Текущее значение скрыто (${f.masked_preview}) — оставьте пустым, чтобы не менять` : (f.default || 'Введите значение')}
                          value={draftValues[f.key] ?? ''}
                          onInput={(e) => setDraftValues((d) => ({ ...d, [f.key]: (e.target as HTMLInputElement).value }))}
                        />
                      </div>
                    ))}
                    {canWriteEnv && (
                      <div class="de-eng-actions" style={{ justifyContent: 'flex-end' }}>
                        <button type="button" class="de-eng-btn" disabled={busy} onClick={() => handleSaveEnv(false)}>
                          Сохранить пресет
                        </button>
                        {(pkg.installed || sandbox) && (canExecute || sandbox) && (
                          <button type="button" class="de-eng-btn primary" disabled={busy} onClick={() => handleSaveEnv(true)}>
                            Сохранить и применить в системный .env
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ color: 'var(--de-muted)' }}>У этого пакета нет шаблона .env.</div>
                )
              )}
            </>
          )}

          {tab === 'install_log' && (
            <pre class="de-eng-log-view">{logs ? logs.install_log : 'Загрузка лога установки...'}</pre>
          )}

          {tab === 'service_logs' && (
            <pre class="de-eng-log-view">{logs ? logs.service_logs : 'Загрузка логов службы...'}</pre>
          )}
        </div>
      </div>
    </div>
  );
}
