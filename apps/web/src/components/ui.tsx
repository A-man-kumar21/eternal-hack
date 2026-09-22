import { useState } from 'react';
import type { ReactNode } from 'react';
import type { DocStatus, Role } from '../api/types';
import { ROLE_LABEL } from '../api/types';

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="loading-block">
      <span className="spinner" aria-hidden /> {label ?? 'Loading…'}
    </div>
  );
}

export function Empty({ icon, title, hint, action }: { icon: string; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="empty">
      <div className="big">{icon}</div>
      <strong style={{ color: 'var(--text)' }}>{title}</strong>
      {hint && <p style={{ margin: '8px 0 0' }}>{hint}</p>}
      {action && <div className="mt">{action}</div>}
    </div>
  );
}

const STATUS_STYLE: Record<DocStatus, string> = {
  INGESTING: 'pill-amber pill-pulse',
  QUARANTINED: 'pill-red',
  ACTIVE: 'pill-green',
  FROZEN: 'pill-blue',
};

export function StatusPill({ status }: { status: DocStatus }) {
  return (
    <span className={`pill ${STATUS_STYLE[status]}`}>
      <span className="dot" /> {status}
    </span>
  );
}

const AV_STYLE: Record<string, string> = {
  clean: 'pill-green',
  skipped: 'pill-amber',
  positive: 'pill-red',
  pending: 'pill-amber pill-pulse',
};

const AV_LABEL: Record<string, string> = {
  clean: '🛡️ Scanned — clean',
  skipped: '⚠️ AV skipped',
  positive: '🦠 AV positive',
  pending: '⏳ AV pending',
};

export function AvBadge({ status, detail }: { status: string; detail?: string | null }) {
  return (
    <span className={`pill ${AV_STYLE[status] ?? ''}`} title={detail ?? undefined}>
      <span className="dot" /> {AV_LABEL[status] ?? status}
    </span>
  );
}

export function RoleBadge({ role }: { role: Role }) {
  return <span className="role-badge">{ROLE_LABEL[role] ?? role}</span>;
}

export function Hash({ value, short }: { value: string; short?: number }) {
  const [copied, setCopied] = useState(false);
  const shown = short ? `${value.slice(0, short)}…` : value;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* clipboard unavailable */
    }
  };
  return (
    <span className="hash" title={value}>
      <span>{shown}</span>
      <button type="button" className="copy-btn" onClick={(e) => { e.stopPropagation(); void copy(); }} title="Copy full hash">
        {copied ? '✓' : '⧉'}
      </button>
    </span>
  );
}

export function ErrorBanner({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  let message = 'Something went wrong.';
  let requestId: string | null = null;
  if (error && typeof error === 'object' && 'friendly' in error) {
    const e = error as { friendly: string; requestId?: string | null };
    message = e.friendly;
    requestId = e.requestId ?? null;
  } else if (error instanceof Error) {
    message = error.message;
  }
  return (
    <div className="banner banner-error" role="alert">
      <span className="icon">⚠️</span>
      <div className="grow">
        <strong>Request failed</strong>
        <div>{message}</div>
        {requestId && <div className="rid">Request ID: {requestId}</div>}
      </div>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>Retry</button>
      )}
    </div>
  );
}

/** Generic modal shell with an optional "reason" field — every privileged action asks for a reason first. */
export function Modal({
  title,
  desc,
  onClose,
  children,
}: {
  title: string;
  desc?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h2>{title}</h2>
        {desc && <p className="desc">{desc}</p>}
        {children}
      </div>
    </div>
  );
}

export function ReasonField({ value, onChange, required }: { value: string; onChange: (v: string) => void; required?: boolean }) {
  return (
    <div className="field">
      <label htmlFor="reason-field">Reason {required ? '(required)' : '(optional)'} — recorded in the audit trail</label>
      <textarea
        id="reason-field"
        className="textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. Court production for Case FIR/2026/0142 — hearing on 28 Sep"
        rows={3}
      />
    </div>
  );
}

/** Truncate long text with a tooltip; used for table cells. */
export function Trunc({ text, max = 42 }: { text?: string; max?: number }) {
  if (!text) return <span style={{ color: 'var(--faint)' }}>—</span>;
  return <span title={text}>{text.length > max ? `${text.slice(0, max)}…` : text}</span>;
}

export function formatTs(ts?: string): string {
  if (!ts) return '—';
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString();
}

export function formatBytes(n?: number): string {
  if (n === undefined || n === null) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}
