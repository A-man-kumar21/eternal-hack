import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import type { DocStatus, Role } from '../api/types';
import { ROLE_LABEL } from '../api/types';
import { EASE, springSnappy } from './motion';

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="loading-block" role="status">
      <span className="spinner" aria-hidden /> {label ?? 'Loading…'}
    </div>
  );
}

/** Shimmer skeleton blocks — layout-stable loading placeholders. */
export function Skeleton({ className = 'sk-line', style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={`skeleton ${className}`} style={style} aria-hidden />;
}

export function SkeletonCards({ count = 6 }: { count?: number }) {
  return (
    <div className="card-grid" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton sk-card" />
      ))}
    </div>
  );
}

export function SkeletonRows({ count = 4 }: { count?: number }) {
  return (
    <div aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton sk-row" style={{ marginBottom: 10 }} />
      ))}
    </div>
  );
}

export function Empty({ icon, title, hint, action }: { icon: string; title: string; hint?: string; action?: ReactNode }) {
  return (
    <motion.div
      className="empty"
      initial={{ opacity: 0, y: 16, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.5, ease: EASE }}
    >
      <motion.div
        className="big"
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 260, damping: 16, delay: 0.08 }}
      >
        {icon}
      </motion.div>
      <strong style={{ color: 'var(--text)' }}>{title}</strong>
      {hint && <p style={{ margin: '8px 0 0', lineHeight: 1.55 }}>{hint}</p>}
      {action && <div className="mt">{action}</div>}
    </motion.div>
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
    <motion.span
      className={`pill ${STATUS_STYLE[status]}`}
      layout
      key={status}
      initial={{ opacity: 0.4, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={springSnappy}
    >
      <span className="dot" /> {status}
    </motion.span>
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
      <motion.button
        type="button"
        className="copy-btn"
        onClick={(e) => { e.stopPropagation(); void copy(); }}
        title="Copy full hash"
        whileTap={{ scale: 0.82 }}
        animate={copied ? { scale: [1, 1.35, 1], color: '#34d399' } : { scale: 1 }}
        transition={{ duration: 0.3 }}
      >
        {copied ? '✓' : '⧉'}
      </motion.button>
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
    <motion.div
      className="banner banner-error"
      role="alert"
      initial={{ opacity: 0, y: -10, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.35, ease: EASE }}
    >
      <span className="icon">⚠️</span>
      <div className="grow">
        <strong>Request failed</strong>
        <div>{message}</div>
        {requestId && <div className="rid">Request ID: {requestId}</div>}
      </div>
      {onRetry && (
        <button type="button" className="btn btn-sm" onClick={onRetry}>Retry</button>
      )}
    </motion.div>
  );
}

/**
 * Generic modal shell with an optional "reason" field — every privileged action asks for a reason first.
 * Always mounted; drive visibility with `open` so enter/exit animations can run.
 */
export function Modal({
  open,
  title,
  desc,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  desc?: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.22 }}
          onClick={onClose}
        >
          <motion.div
            className="modal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: 28, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 14, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 380, damping: 32 }}
          >
            <h2>{title}</h2>
            {desc && <p className="desc">{desc}</p>}
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
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
