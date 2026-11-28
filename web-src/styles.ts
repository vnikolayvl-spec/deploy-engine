// Скопированные CSS-стили модуля Deploy Engine поверх дизайн-токенов --de-* панели de-web

export const MODULE_STYLES = `
.de-eng-root {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: var(--de-text);
  font-family: var(--de-font-sans);
  font-size: 13px;
  line-height: 1.45;
}

.de-eng-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--de-border);
}

.de-eng-seg {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  background: var(--de-surface-2);
  border: 1px solid var(--de-border);
  border-radius: var(--de-radius);
}

.de-eng-seg-btn {
  padding: 6px 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--de-muted);
  background: transparent;
  border: none;
  border-radius: var(--de-radius-sm);
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 140ms ease, color 140ms ease;
}

.de-eng-seg-btn:hover {
  color: var(--de-text);
}

.de-eng-seg-btn.active {
  background: var(--de-surface);
  color: var(--de-text);
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.de-eng-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.de-eng-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 14px;
  font-family: var(--de-font-sans);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
  white-space: nowrap;
  border-radius: var(--de-radius);
  border: 1px solid var(--de-border);
  background: var(--de-surface);
  color: var(--de-text);
  cursor: pointer;
  transition: background-color 140ms ease, border-color 140ms ease, opacity 140ms ease;
}

.de-eng-btn:hover:not(:disabled) {
  background: var(--de-surface-2);
  border-color: var(--de-border-strong);
}

.de-eng-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.de-eng-btn.primary {
  background: var(--de-accent);
  border-color: var(--de-accent);
  color: var(--de-accent-fg);
  font-weight: 600;
}

.de-eng-btn.primary:hover:not(:disabled) {
  background: var(--de-accent-hover);
  border-color: var(--de-accent-hover);
}

.de-eng-btn.danger {
  border-color: var(--de-danger);
  color: var(--de-danger);
  background: transparent;
}

.de-eng-btn.danger:hover:not(:disabled) {
  background: var(--de-danger);
  color: #ffffff;
}

.de-eng-btn.sm {
  padding: 4px 10px;
  font-size: 12px;
}

.de-eng-btn.xs {
  padding: 3px 8px;
  font-size: 11px;
}

.de-eng-workspace {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr) 268px;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1160px) {
  .de-eng-workspace {
    grid-template-columns: 1fr;
  }
}

.de-eng-panel {
  background: var(--de-surface);
  border: 1px solid var(--de-border);
  border-radius: var(--de-radius-lg);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.de-eng-panel-title {
  font-family: var(--de-font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--de-text);
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.de-eng-meta {
  font-size: 12px;
  color: var(--de-muted);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.de-eng-mono {
  font-family: var(--de-font-mono);
  font-variant-numeric: tabular-nums;
}

.de-eng-input, .de-eng-select {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 10px;
  font-family: var(--de-font-sans);
  font-size: 13px;
  color: var(--de-text);
  background: var(--de-bg);
  border: 1px solid var(--de-border);
  border-radius: var(--de-radius);
  outline: none;
}

.de-eng-input:focus, .de-eng-select:focus {
  border-color: var(--de-accent);
}

.de-eng-sidebar-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 520px;
  overflow-y: auto;
}

.de-eng-sidebar-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 7px 10px;
  border: none;
  border-radius: var(--de-radius-sm);
  background: transparent;
  color: var(--de-text);
  font-size: 13px;
  cursor: pointer;
}

.de-eng-sidebar-item:hover {
  background: var(--de-surface-2);
}

.de-eng-sidebar-item.active {
  background: var(--de-accent-subtle);
  color: var(--de-accent);
  font-weight: 600;
}

.de-eng-tree-scroll {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 440px;
  overflow-y: auto;
  padding-right: 4px;
}

.de-eng-cat-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  background: var(--de-surface-2);
  border-radius: var(--de-radius-sm);
  cursor: pointer;
  user-select: none;
  font-weight: 600;
  color: var(--de-text);
}

.de-eng-pkg-row {
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid var(--de-border);
  padding: 8px 6px;
  gap: 6px;
}

.de-eng-pkg-row:last-child {
  border-bottom: none;
}

.de-eng-pkg-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.de-eng-pkg-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.de-eng-expand-btn {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--de-border);
  border-radius: 4px;
  background: var(--de-bg);
  color: var(--de-muted);
  cursor: pointer;
  font-family: var(--de-font-mono);
  font-size: 11px;
  flex-shrink: 0;
}

.de-eng-pkg-name {
  font-weight: 600;
  color: var(--de-text);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
}

.de-eng-pkg-name:hover {
  color: var(--de-accent);
  text-decoration: underline;
}

.de-eng-units-box {
  margin-left: 28px;
  padding: 6px 0 4px 12px;
  border-top: 1px dashed var(--de-border);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.de-eng-unit-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
  padding: 3px 0;
}

.de-eng-check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: var(--de-text);
}

.de-eng-status-ok { color: var(--de-success); font-weight: 600; }
.de-eng-status-warn { color: var(--de-warning); font-weight: 600; }
.de-eng-status-err { color: var(--de-danger); font-weight: 600; }
.de-eng-status-accent { color: var(--de-accent); font-weight: 600; }

.de-eng-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 900;
  padding: 20px;
}

.de-eng-modal {
  width: min(980px, 96vw);
  max-height: 90vh;
  background: var(--de-bg);
  border: 1px solid var(--de-border-strong);
  border-radius: var(--de-radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
}

.de-eng-modal-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--de-border);
  background: var(--de-surface);
}

.de-eng-modal-body {
  padding: 18px 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  flex: 1;
}

.de-eng-modal-ftr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-top: 1px solid var(--de-border);
  background: var(--de-surface);
}

.de-eng-log-view {
  background: #0b1120;
  color: #e2e8f0;
  font-family: var(--de-font-mono);
  font-size: 12px;
  line-height: 1.5;
  padding: 12px 14px;
  border-radius: var(--de-radius);
  border: 1px solid var(--de-border);
  max-height: 400px;
  min-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.de-eng-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 12px;
}

.de-eng-table th {
  padding: 8px 10px;
  border-bottom: 1px solid var(--de-border);
  color: var(--de-muted);
  font-weight: 600;
  white-space: nowrap;
}

.de-eng-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--de-border);
  vertical-align: top;
}

.de-eng-table tr:hover td {
  background: var(--de-surface-2);
}

.de-eng-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: var(--de-accent-subtle);
  border: 1px solid var(--de-border);
  border-radius: var(--de-radius);
}
`;
