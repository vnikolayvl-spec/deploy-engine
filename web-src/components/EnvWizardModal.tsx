// Мастер обязательного подтверждения .env перед запуском плана (аналог PackageEnvPanel в TUI)

import { h } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import type { DeModuleSdk } from '../../../web-sdk/types';
import type { EnvFormData, SandboxOs } from '../types';

interface Props {
  sdk: DeModuleSdk;
  pendingPackages: string[];
  sandbox: boolean;
  sandboxOs: SandboxOs;
  onCancel: () => void;
  onAllConfirmed: () => void;
}

export function EnvWizardModal(props: Props) {
  const { sdk, pendingPackages, sandbox, sandboxOs, onCancel, onAllConfirmed } = props;
  const [idx, setIdx] = useState(0);
  const [form, setForm] = useState<EnvFormData | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const curPkg = pendingPackages[idx];

  useEffect(() => {
    if (!curPkg) {
      onAllConfirmed();
      return;
    }
    let active = true;
    setLoading(true);
    sdk.api.call<EnvFormData>('get_env_form', {
      package: curPkg, reveal: false, sandbox, sandbox_os: sandboxOs,
    }).then((res) => {
      if (!active) return;
      setForm(res);
      const draft: Record<string, string> = {};
      for (const f of res.fields) {
        draft[f.key] = f.value;
      }
      setValues(draft);
    }).catch((err) => {
      if (active) sdk.notifyToast(`Ошибка загрузки .env для ${curPkg}: ${err.message}`, 'error');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [curPkg, sandbox, sandboxOs]);

  const missingRequired = form
    ? form.fields.filter((f) => {
        if (!f.required) return false;
        const v = (values[f.key] ?? '').trim();
        return !v && !(f.is_secret && f.has_existing_value);
      })
    : [];

  const handleConfirmStep = async () => {
    if (!curPkg || missingRequired.length > 0) return;
    setSaving(true);
    try {
      await sdk.api.call('save_env_preset', {
        package: curPkg,
        values,
        apply_system: false,
        sandbox,
        sandbox_os: sandboxOs,
      });
      sdk.notifyToast(`Пресет .env для «${curPkg}» подтверждён`, 'success');
      if (idx + 1 >= pendingPackages.length) {
        onAllConfirmed();
      } else {
        setIdx(idx + 1);
      }
    } catch (err: any) {
      sdk.notifyToast(err.message || 'Ошибка сохранения пресета', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div class="de-eng-backdrop">
      <div class="de-eng-modal" role="dialog" aria-modal="true" aria-label="Подтверждение .env перед запуском">
        <div class="de-eng-modal-hdr">
          <div>
            <div style={{ fontFamily: 'var(--de-font-display)', fontSize: '16px', fontWeight: 700 }}>
              Подтверждение .env перед выполнением плана
            </div>
            <div class="de-eng-meta de-eng-mono">
              <span>Шаг {Math.min(idx + 1, pendingPackages.length)} из {pendingPackages.length}</span>
              <span>·</span>
              <span>Пакет: {curPkg}</span>
            </div>
          </div>
          <button type="button" class="de-eng-btn sm" onClick={onCancel}>Отмена</button>
        </div>

        <div class="de-eng-modal-body">
          {loading || !form ? (
            <div style={{ color: 'var(--de-muted)' }}>Загрузка шаблона .env...</div>
          ) : (
            <>
              <div class="de-eng-meta">
                Заполните обязательные параметры или укажите маркеры <span class="de-eng-mono">#AUTO#</span>,{' '}
                <span class="de-eng-mono">#GEN#</span> или <span class="de-eng-mono">#SKIP#</span>.
                Пресет сохраняется с правами 0600 до начала установки.
              </div>
              {form.fields.map((f) => {
                const isMissing = f.required && !(values[f.key] ?? '').trim() && !(f.is_secret && f.has_existing_value);
                return (
                  <div key={f.key} style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingBottom: '10px', borderBottom: '1px solid var(--de-border)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', flexWrap: 'wrap' }}>
                      <label class="de-eng-mono" style={{ fontWeight: 600 }}>
                        {f.key}
                        {f.required && (
                          <span class={isMissing ? 'de-eng-status-err' : 'de-eng-status-ok'} style={{ marginLeft: '6px' }}>
                            {isMissing ? 'Обязательно' : 'Заполнено'}
                          </span>
                        )}
                      </label>
                      <div class="de-eng-actions">
                        <button type="button" class="de-eng-btn xs" onClick={() => setValues((v) => ({ ...v, [f.key]: '#AUTO#' }))}>#AUTO#</button>
                        <button type="button" class="de-eng-btn xs" onClick={() => setValues((v) => ({ ...v, [f.key]: '#GEN#' }))}>#GEN#</button>
                        <button type="button" class="de-eng-btn xs" onClick={() => setValues((v) => ({ ...v, [f.key]: '#SKIP#' }))}>#SKIP#</button>
                      </div>
                    </div>
                    {(f.prompt_label || f.comment) && (
                      <div style={{ fontSize: '12px', color: 'var(--de-muted)' }}>{f.prompt_label || f.comment}</div>
                    )}
                    <input
                      type={f.is_secret ? 'password' : 'text'}
                      class="de-eng-input de-eng-mono"
                      placeholder={f.is_secret && f.has_existing_value ? `Секрет сохранён (${f.masked_preview})` : (f.default || 'Введите значение')}
                      value={values[f.key] ?? ''}
                      onInput={(e) => setValues((v) => ({ ...v, [f.key]: (e.target as HTMLInputElement).value }))}
                    />
                  </div>
                );
              })}
            </>
          )}
        </div>

        <div class="de-eng-modal-ftr">
          <div style={{ fontSize: '12px', color: missingRequired.length > 0 ? 'var(--de-danger)' : 'var(--de-muted)' }}>
            {missingRequired.length > 0
              ? `Не заполнены обязательные поля: ${missingRequired.map((m) => m.key).join(', ')}`
              : 'Все обязательные параметры заполнены.'}
          </div>
          <div class="de-eng-actions">
            <button type="button" class="de-eng-btn" onClick={onCancel}>Отменить план</button>
            <button
              type="button"
              class="de-eng-btn primary"
              disabled={saving || loading || missingRequired.length > 0}
              onClick={handleConfirmStep}
            >
              {saving
                ? 'Сохранение...'
                : idx + 1 >= pendingPackages.length
                  ? 'Принять .env и запустить план'
                  : 'Принять .env и далее'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
