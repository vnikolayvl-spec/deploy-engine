// Дерево пакетов, юнитов и бэкапов с сохранением раскрытых веток

import { h } from 'preact';
import { useMemo } from 'preact/hooks';
import type { FilterMode, PackageAction, PackageSummary } from '../types';

interface Props {
  packages: PackageSummary[];
  categories: Record<string, string>;
  search: string;
  onSearchChange: (val: string) => void;
  filter: FilterMode;
  onFilterChange: (f: FilterMode) => void;
  expandedKeys: Set<string>;
  onToggleExpand: (key: string) => void;
  actions: Record<string, PackageAction>;
  unitUpdates: Record<string, string[]>;
  backups: string[];
  restores: Record<string, string>;
  onSetAction: (pkgKey: string, action: PackageAction | null) => void;
  onToggleUnit: (pkgKey: string, unitName: string) => void;
  onToggleBackup: (pkgName: string) => void;
  onSetRestore: (pkgName: string, selector: string) => void;
  onOpenDetails: (pkg: PackageSummary, initialTab?: 'info' | 'env' | 'install_log' | 'service_logs') => void;
  canWriteEnv: boolean;
}

const UNIT_TYPE_LABELS: Record<string, string> = {
  web: 'Web',
  file: 'Файлы',
  script: 'Скрипт',
  unit: 'Служба',
  service: 'Служба',
  timer: 'Таймер',
  env: 'ENV',
  data: 'Данные',
  symlink: 'Симлинк',
};

export function PackageTreePanel(props: Props) {
  const {
    packages, categories, search, onSearchChange, filter, onFilterChange,
    expandedKeys, onToggleExpand, actions, unitUpdates, backups, restores,
    onSetAction, onToggleUnit, onToggleBackup, onSetRestore, onOpenDetails,
  } = props;

  const grouped = useMemo(() => {
    const q = search.trim().toLowerCase();
    const map = new Map<string, PackageSummary[]>();
    for (const pkg of packages) {
      const hasPlan = Boolean(
        actions[pkg.key] ||
        (unitUpdates[pkg.key] && unitUpdates[pkg.key].length > 0) ||
        backups.includes(pkg.name) ||
        restores[pkg.name]
      );
      if (filter === 'installed' && !pkg.installed) continue;
      if (filter === 'planned' && !hasPlan) continue;
      if (filter === 'updates' && pkg.update_status !== 'upgrade') continue;
      if (q) {
        const hay = `${pkg.key} ${pkg.name} ${pkg.desc} ${pkg.category}`.toLowerCase();
        if (!hay.includes(q)) continue;
      }
      const cat = pkg.category || 'корень';
      if (!map.has(cat)) map.set(cat, []);
      map.get(cat)!.push(pkg);
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b, 'ru'));
  }, [packages, search, filter, actions, unitUpdates, backups, restores]);

  const counts = useMemo(() => {
    let installed = 0;
    let updates = 0;
    let planned = 0;
    for (const p of packages) {
      if (p.installed) installed++;
      if (p.update_status === 'upgrade') updates++;
      if (actions[p.key] || (unitUpdates[p.key]?.length ?? 0) > 0 || backups.includes(p.name) || restores[p.name]) {
        planned++;
      }
    }
    return { total: packages.length, installed, updates, planned };
  }, [packages, actions, unitUpdates, backups, restores]);

  return (
    <div class="de-eng-panel">
      <div class="de-eng-panel-title">
        <span>Дерево пакетов и юнитов</span>
        <span class="de-eng-meta de-eng-mono">
          Всего {counts.total} · Установлено {counts.installed} · Обновлений {counts.updates}
        </span>
      </div>

      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="search"
          class="de-eng-input"
          style={{ flex: '1 1 200px' }}
          placeholder="Поиск по имени, категории или описанию..."
          value={search}
          onInput={(e) => onSearchChange((e.target as HTMLInputElement).value)}
        />
        <div class="de-eng-seg" role="tablist" aria-label="Фильтр пакетов">
          {([
            ['all', `Все (${counts.total})`],
            ['installed', `Установленные (${counts.installed})`],
            ['planned', `С планом (${counts.planned})`],
            ['updates', `Обновления (${counts.updates})`],
          ] as [FilterMode, string][]).map(([key, label]) => (
            <button
              key={key}
              type="button"
              class={`de-eng-seg-btn ${filter === key ? 'active' : ''}`}
              onClick={() => onFilterChange(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div class="de-eng-tree-scroll">
        {grouped.length === 0 ? (
          <div style={{ padding: '24px 12px', textAlign: 'center', color: 'var(--de-muted)' }}>
            Пакеты по текущему фильтру не найдены. Попробуйте очистить поиск или выполнить обновление базы пакетов.
          </div>
        ) : (
          grouped.map(([cat, list]) => {
            const catKey = `cat:${cat}`;
            const catOpen = expandedKeys.has(catKey);
            const catDesc = categories[cat] || '';
            return (
              <div key={cat}>
                <div
                  class="de-eng-cat-hdr"
                  role="button"
                  tabIndex={0}
                  onClick={() => onToggleExpand(catKey)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggleExpand(catKey); } }}
                >
                  <span>
                    <span class="de-eng-mono" style={{ marginRight: '8px', color: 'var(--de-muted)' }}>
                      {catOpen ? '▼' : '▶'}
                    </span>
                    {cat}
                    {catDesc ? (
                      <span style={{ fontWeight: 400, color: 'var(--de-muted)', marginLeft: '8px', fontSize: '12px' }}>
                        — {catDesc}
                      </span>
                    ) : null}
                  </span>
                  <span class="de-eng-mono" style={{ fontSize: '12px', color: 'var(--de-muted)' }}>
                    {list.length}
                  </span>
                </div>

                {catOpen && (
                  <div style={{ paddingLeft: '6px' }}>
                    {list.map((pkg) => {
                      const pkgOpen = expandedKeys.has(pkg.key);
                      const curAct = actions[pkg.key] || null;
                      const selUnits = unitUpdates[pkg.key] || [];
                      const isBackup = backups.includes(pkg.name);
                      const restoreSel = restores[pkg.name] || '';

                      return (
                        <div key={pkg.key} class="de-eng-pkg-row" style={{ opacity: pkg.compatible ? 1 : 0.55 }}>
                          <div class="de-eng-pkg-main">
                            <div class="de-eng-pkg-left">
                              <button
                                type="button"
                                class="de-eng-expand-btn"
                                title={pkgOpen ? 'Свернуть юниты и бэкапы' : 'Раскрыть юниты и бэкапы'}
                                onClick={() => onToggleExpand(pkg.key)}
                              >
                                {pkgOpen ? '−' : '+'}
                              </button>
                              <div style={{ minWidth: 0 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                  <button
                                    type="button"
                                    class="de-eng-pkg-name"
                                    onClick={() => onOpenDetails(pkg, 'info')}
                                  >
                                    {pkg.name}
                                  </button>
                                  <span class="de-eng-meta de-eng-mono">
                                    {pkg.installed ? (
                                      pkg.update_status === 'upgrade' ? (
                                        <span class="de-eng-status-warn">
                                          v{pkg.installed_version} → v{pkg.available_version}
                                        </span>
                                      ) : (
                                        <span class="de-eng-status-ok">Установлен · v{pkg.installed_version}</span>
                                      )
                                    ) : (
                                      <span>v{pkg.available_version}</span>
                                    )}
                                    {!pkg.compatible && <span class="de-eng-status-err">· Несовместим</span>}
                                    {pkg.is_external && <span>· Внешний</span>}
                                    {!pkg.manifest_available && <span class="de-eng-status-warn">· Манифест удалён</span>}
                                    {selUnits.length > 0 && (
                                      <span class="de-eng-status-accent">· Юниты: {selUnits.join(', ')}</span>
                                    )}
                                  </span>
                                </div>
                                {pkg.desc && (
                                  <div style={{ fontSize: '12px', color: 'var(--de-muted)', marginTop: '2px' }}>
                                    {pkg.desc}
                                  </div>
                                )}
                              </div>
                            </div>

                            <div class="de-eng-actions">
                              {pkg.has_env && (
                                <button
                                  type="button"
                                  class="de-eng-btn xs"
                                  title="Просмотр и редактирование .env"
                                  onClick={() => onOpenDetails(pkg, 'env')}
                                >
                                  {pkg.has_preset ? '.env (пресет)' : '.env'}
                                </button>
                              )}
                              {!pkg.installed ? (
                                <button
                                  type="button"
                                  class={`de-eng-btn xs ${curAct === 'install' ? 'primary' : ''}`}
                                  disabled={!pkg.compatible || !pkg.manifest_available}
                                  onClick={() => onSetAction(pkg.key, curAct === 'install' ? null : 'install')}
                                >
                                  {curAct === 'install' ? '✓ Установить' : 'Установить'}
                                </button>
                              ) : (
                                <>
                                  <button
                                    type="button"
                                    class={`de-eng-btn xs ${curAct === 'reinstall' ? 'primary' : ''}`}
                                    disabled={!pkg.compatible || !pkg.manifest_available}
                                    onClick={() => onSetAction(pkg.key, curAct === 'reinstall' ? null : 'reinstall')}
                                  >
                                    {curAct === 'reinstall'
                                      ? (pkg.update_status === 'upgrade' ? '✓ Обновить' : '✓ Переустановить')
                                      : (pkg.update_status === 'upgrade' ? 'Обновить' : 'Переустановить')}
                                  </button>
                                  <button
                                    type="button"
                                    class={`de-eng-btn xs ${curAct === 'uninstall' ? 'danger' : ''}`}
                                    onClick={() => onSetAction(pkg.key, curAct === 'uninstall' ? null : 'uninstall')}
                                  >
                                    {curAct === 'uninstall' ? '✓ Удалить' : 'Удалить'}
                                  </button>
                                </>
                              )}
                            </div>
                          </div>

                          {pkgOpen && (
                            <div class="de-eng-units-box">
                              {pkg.units.length > 0 && (
                                <>
                                  <div style={{ fontSize: '11px', color: 'var(--de-muted)', fontWeight: 600 }}>
                                    Юниты пакета {pkg.installed ? '(отметьте для точечного обновления)' : ''}
                                  </div>
                                  {pkg.units.map((u) => {
                                    const checked = selUnits.includes(u.name);
                                    const canSelectUnit = pkg.installed && pkg.compatible && pkg.manifest_available && u.type !== 'data';
                                    return (
                                      <div key={u.name} class="de-eng-unit-row">
                                        <label class="de-eng-check-row" style={{ fontSize: '12px' }}>
                                          {canSelectUnit && (
                                            <input
                                              type="checkbox"
                                              checked={checked}
                                              onChange={() => onToggleUnit(pkg.key, u.name)}
                                            />
                                          )}
                                          <span class="de-eng-mono" style={{ color: 'var(--de-accent)', minWidth: '58px' }}>
                                            {UNIT_TYPE_LABELS[u.type] || u.type}
                                          </span>
                                          <span class="de-eng-mono" style={{ fontWeight: 500 }}>{u.name}</span>
                                          {u.dest && (
                                            <span class="de-eng-mono" style={{ color: 'var(--de-muted)' }}>→ {u.dest}</span>
                                          )}
                                        </label>
                                        {u.type === 'env' && (
                                          <button
                                            type="button"
                                            class="de-eng-btn xs"
                                            onClick={() => onOpenDetails(pkg, 'env')}
                                          >
                                            Открыть .env
                                          </button>
                                        )}
                                      </div>
                                    );
                                  })}
                                </>
                              )}

                              {pkg.installed && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', paddingTop: '4px' }}>
                                  <label class="de-eng-check-row" style={{ fontSize: '12px' }}>
                                    <input
                                      type="checkbox"
                                      checked={isBackup}
                                      onChange={() => onToggleBackup(pkg.name)}
                                    />
                                    <span>Создать бэкап перед выполнением</span>
                                  </label>
                                  {pkg.backups.length > 0 && (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                      <span style={{ fontSize: '12px', color: 'var(--de-muted)' }}>Восстановить:</span>
                                      <select
                                        class="de-eng-select"
                                        style={{ width: 'auto', padding: '3px 8px', fontSize: '12px' }}
                                        value={restoreSel}
                                        onChange={(e) => onSetRestore(pkg.name, (e.target as HTMLSelectElement).value)}
                                      >
                                        <option value="">Не восстанавливать</option>
                                        {pkg.backups.map((b, i) => (
                                          <option key={b.filename} value={b.filename}>
                                            #{i + 1} · {b.timestamp} ({b.size_human}){b.comment ? ` — ${b.comment}` : ''}
                                          </option>
                                        ))}
                                      </select>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
