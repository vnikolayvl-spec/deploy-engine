// Монитор выполнения фоновой задачи: общий лог, вкладки по пакетам, live polling и отмена (SIGINT -> LIFO)

import { h } from 'preact';
import { useEffect, useMemo, useRef, useState } from 'preact/hooks';
import type { DeModuleSdk } from '../../../web-sdk/types';
import type { JobEvent, JobRecord } from '../types';

interface Props {
  sdk: DeModuleSdk;
  jobId: string;
  onClose: () => void;
  onFinished?: () => void;
}

const STATUS_LABELS: Record<string, { text: string; cls: string }> = {
  queued: { text: 'В очереди', cls: '' },
  running: { text: 'Выполняется', cls: 'de-eng-status-accent' },
  succeeded: { text: 'Успешно', cls: 'de-eng-status-ok' },
  done: { text: 'Готово', cls: 'de-eng-status-ok' },
  failed: { text: 'Ошибка', cls: 'de-eng-status-err' },
  cancelled: { text: 'Отменено', cls: 'de-eng-status-warn' },
  skipped: { text: 'Пропущено', cls: '' },
};

const MODE_LABELS: Record<string, string> = {
  live: 'Боевой режим',
  sandbox: 'Sandbox (песочница)',
  dry_run: 'Dry-Run (симуляция)',
};

export function JobMonitorModal(props: Props) {
  const { sdk, jobId, onClose, onFinished } = props;
  const [job, setJob] = useState<JobRecord | null>(null);
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [activeTab, setActiveTab] = useState<string>('__all__');
  const [autoScroll, setAutoScroll] = useState(true);
  const [cancelling, setCancelling] = useState(false);
  const [elapsedSec, setElapsedSec] = useState(0);

  const offsetRef = useRef(0);
  const finishedNotifiedRef = useRef(false);
  const logBoxRef = useRef<HTMLPreElement | null>(null);

  const isRunning = job ? (job.status === 'queued' || job.status === 'running') : true;

  useEffect(() => {
    offsetRef.current = 0;
    finishedNotifiedRef.current = false;
    setEvents([]);
    setJob(null);
    setActiveTab('__all__');
  }, [jobId]);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const res = await sdk.api.call<{ job: JobRecord; events: JobEvent[]; next_offset: number }>('get_job_status', {
          job_id: jobId,
          offset: offsetRef.current,
        });
        if (!alive) return;
        setJob(res.job);
        if (res.events && res.events.length > 0) {
          offsetRef.current = res.next_offset;
          setEvents((prev) => prev.concat(res.events));
        }
        const stillActive = res.job.status === 'queued' || res.job.status === 'running';
        if (stillActive) {
          timer = setTimeout(poll, 800);
        } else if (!finishedNotifiedRef.current) {
          finishedNotifiedRef.current = true;
          onFinished?.();
        }
      } catch (err: any) {
        if (!alive) return;
        sdk.notifyToast(`Ошибка опроса задачи: ${err.message}`, 'error');
      }
    };

    poll();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [jobId]);

  useEffect(() => {
    if (!isRunning) return;
    const t0 = Date.now();
    const id = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - t0) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [isRunning, jobId]);

  const filteredLines = useMemo(() => {
    if (activeTab === '__all__') return events;
    return events.filter((e) => e.pkg === activeTab);
  }, [events, activeTab]);

  useEffect(() => {
    if (autoScroll && logBoxRef.current) {
      logBoxRef.current.scrollTop = logBoxRef.current.scrollHeight;
    }
  }, [filteredLines, autoScroll]);

  const handleCancel = async () => {
    const ok = await sdk.requestConfirm({
      title: 'Остановить выполнение плана?',
      message: 'Воркеру будет отправлен сигнал SIGINT для прерывания операции и запуска атомарного LIFO-отката транзакции.',
      confirmText: 'Остановить и откатить',
      danger: true,
    });
    if (!ok) return;
    setCancelling(true);
    try {
      await sdk.api.call('cancel_job', { job_id: jobId });
      sdk.notifyToast('Запрос на остановку задачи отправлен (SIGINT)', 'warning');
    } catch (err: any) {
      sdk.notifyToast(`Не удалось отменить задачу: ${err.message}`, 'error');
    } finally {
      setCancelling(false);
    }
  };

  const stMeta = STATUS_LABELS[job?.status || 'queued'] || { text: job?.status || '—', cls: '' };
  const durationLabel = job && !isRunning
    ? `${job.duration_sec.toFixed(1)} с`
    : `${String(Math.floor(elapsedSec / 60)).padStart(2, '0')}:${String(elapsedSec % 60).padStart(2, '0')}`;

  return (
    <div class="de-eng-backdrop" onClick={(e) => { if (!isRunning && e.target === e.currentTarget) onClose(); }}>
      <div class="de-eng-modal" role="dialog" aria-modal="true" aria-label={`Монитор задачи ${jobId}`}>
        <div class="de-eng-modal-hdr">
          <div>
            <div style={{ fontFamily: 'var(--de-font-display)', fontSize: '16px', fontWeight: 700 }}>
              Выполнение плана · <span class="de-eng-mono">{jobId}</span>
            </div>
            <div class="de-eng-meta de-eng-mono">
              <span class={stMeta.cls}>{stMeta.text}</span>
              <span>·</span>
              <span>{MODE_LABELS[job?.mode || 'live'] || job?.mode}</span>
              <span>·</span>
              <span>Время: {durationLabel}</span>
              {job?.phase && <span>· {job.phase}</span>}
            </div>
          </div>
          <div class="de-eng-actions">
            {isRunning && sdk.can('jobs.cancel') && (
              <button type="button" class="de-eng-btn danger sm" disabled={cancelling} onClick={handleCancel}>
                {cancelling ? 'Отмена...' : 'Отменить задачу (SIGINT)'}
              </button>
            )}
            <button type="button" class="de-eng-btn sm" onClick={onClose}>
              {isRunning ? 'Свернуть в фон' : 'Закрыть'}
            </button>
          </div>
        </div>

        <div style={{ padding: '10px 20px', borderBottom: '1px solid var(--de-border)', background: 'var(--de-surface)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <div class="de-eng-seg" style={{ overflowX: 'auto', maxWidth: '100%' }}>
            <button
              type="button"
              class={`de-eng-seg-btn ${activeTab === '__all__' ? 'active' : ''}`}
              onClick={() => setActiveTab('__all__')}
            >
              Общий лог ({events.length})
            </button>
            {(job?.ordered_packages || []).map((pkg) => {
              const pSt = job?.package_statuses?.[pkg] || 'queued';
              const pMeta = STATUS_LABELS[pSt] || { text: pSt, cls: '' };
              return (
                <button
                  key={pkg}
                  type="button"
                  class={`de-eng-seg-btn ${activeTab === pkg ? 'active' : ''}`}
                  onClick={() => setActiveTab(pkg)}
                >
                  {pkg} · <span class={pMeta.cls}>{pMeta.text}</span>
                </button>
              );
            })}
          </div>
          <label class="de-eng-check-row" style={{ fontSize: '12px' }}>
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll((e.target as HTMLInputElement).checked)} />
            <span>Автопрокрутка</span>
          </label>
        </div>

        <div class="de-eng-modal-body">
          {job?.error && (
            <div style={{ padding: '10px 12px', border: '1px solid var(--de-danger)', borderRadius: 'var(--de-radius)', color: 'var(--de-danger)', fontSize: '13px' }}>
              {job.error}
            </div>
          )}
          <pre ref={logBoxRef} class="de-eng-log-view">
            {filteredLines.length === 0
              ? (isRunning ? 'Ожидание вывода от воркера...' : 'Для этой вкладки нет записей журнала.')
              : filteredLines.map((ev, i) => (
                <div
                  key={i}
                  style={{
                    color: ev.level === 'error'
                      ? '#fca5a5'
                      : ev.level === 'warning'
                        ? '#fcd34d'
                        : ev.level === 'success'
                          ? '#86efac'
                          : '#e2e8f0',
                  }}
                >
                  <span style={{ color: '#64748b' }}>[{ev.ts || '--:--:--'}]</span>
                  {activeTab === '__all__' && ev.pkg ? <span style={{ color: '#38bdf8' }}> [{ev.pkg}]</span> : null}{' '}
                  {ev.line}
                </div>
              ))}
          </pre>
        </div>

        <div class="de-eng-modal-ftr">
          <div class="de-eng-meta de-eng-mono">
            Инициатор: {job?.actor?.username || '—'} ({job?.actor?.role || '—'}) · Создана: {job?.created_at || '—'}
          </div>
          <button type="button" class="de-eng-btn" onClick={onClose}>
            {isRunning ? 'Свернуть' : 'Готово'}
          </button>
        </div>
      </div>
    </div>
  );
}
