// Вкладка истории запусков и аудита выполненных планов Deploy Engine

import { h } from 'preact';
import type { JobRecord } from '../types';

interface Props {
  jobs: JobRecord[];
  loading: boolean;
  onRefresh: () => void;
  onOpenJob: (jobId: string) => void;
}

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  queued: { label: 'В очереди', cls: '' },
  running: { label: 'Выполняется', cls: 'de-eng-status-accent' },
  succeeded: { label: 'Успешно', cls: 'de-eng-status-ok' },
  failed: { label: 'Ошибка', cls: 'de-eng-status-err' },
  cancelled: { label: 'Отменено', cls: 'de-eng-status-warn' },
};

const MODE_MAP: Record<string, string> = {
  live: 'Боевой',
  sandbox: 'Sandbox',
  dry_run: 'Dry-Run',
};

export function JobHistoryTab(props: Props) {
  const { jobs, loading, onRefresh, onOpenJob } = props;

  return (
    <div class="de-eng-panel">
      <div class="de-eng-panel-title">
        <span>История запусков и аудит планов</span>
        <button type="button" class="de-eng-btn sm" disabled={loading} onClick={onRefresh}>
          {loading ? 'Обновление...' : 'Обновить список'}
        </button>
      </div>

      {jobs.length === 0 ? (
        <div style={{ padding: '28px 12px', textAlign: 'center', color: 'var(--de-muted)' }}>
          {loading ? 'Загрузка истории запусков...' : 'История запусков пока пуста. Выполните любой план во вкладке «Оркестратор».'}
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table class="de-eng-table">
            <thead>
              <tr>
                <th>Дата / ID задачи</th>
                <th>Инициатор</th>
                <th>Режим</th>
                <th>Пакеты в плане</th>
                <th>Статус</th>
                <th style={{ textAlign: 'right' }}>Длительность</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => {
                const st = STATUS_MAP[j.status] || { label: j.status, cls: '' };
                return (
                  <tr key={j.job_id}>
                    <td class="de-eng-mono">
                      <div>{j.created_at}</div>
                      <div style={{ color: 'var(--de-muted)', fontSize: '11px' }}>{j.job_id}</div>
                    </td>
                    <td>
                      <div>{j.actor?.username || '—'}</div>
                      <div style={{ color: 'var(--de-muted)', fontSize: '11px' }}>{j.actor?.role || ''}</div>
                    </td>
                    <td class="de-eng-mono">{MODE_MAP[j.mode] || j.mode}</td>
                    <td class="de-eng-mono">
                      {j.ordered_packages.length > 0 ? j.ordered_packages.join(', ') : '—'}
                    </td>
                    <td>
                      <span class={st.cls}>{st.label}</span>
                      {j.error && (
                        <div style={{ color: 'var(--de-danger)', fontSize: '11px', maxWidth: '240px' }}>
                          {j.error}
                        </div>
                      )}
                    </td>
                    <td class="de-eng-mono" style={{ textAlign: 'right' }}>
                      {j.duration_sec ? `${j.duration_sec.toFixed(1)} с` : '—'}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button type="button" class="de-eng-btn xs" onClick={() => onOpenJob(j.job_id)}>
                        Открыть лог
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
