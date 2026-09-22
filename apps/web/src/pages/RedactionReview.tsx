import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiGet, apiPost } from '../api/client';
import type { AnalyzeResponse, DerivativeInfo, Document, Version } from '../api/types';
import {
  Empty, ErrorBanner, Hash, ReasonField, Spinner, formatBytes, formatTs,
} from '../components/ui';

const LABEL_PILL: Record<string, string> = {
  AADHAAR: 'pill-red', PHONE: 'pill-amber', EMAIL: 'pill-blue', NAME: 'pill-violet',
};

export default function RedactionReview() {
  const { id: caseId = '', docId = '' } = useParams();
  const [approvals, setApprovals] = useState<Record<string, boolean>>({});
  const [reason, setReason] = useState('');
  const [result, setResult] = useState<DerivativeInfo | null>(null);

  const docQuery = useQuery({
    queryKey: ['document', docId],
    queryFn: () => apiGet<Document>(`/documents/${docId}`),
  });
  const derivQuery = useQuery({
    queryKey: ['derivatives', docId],
    queryFn: () => apiGet<Version[]>(`/documents/${docId}/derivatives`),
    enabled: !!docId,
  });

  const analyzeMut = useMutation({
    mutationFn: () => apiPost<AnalyzeResponse>(`/documents/${docId}/redactions/analyze`),
    onSuccess: (r) => {
      const init: Record<string, boolean> = {};
      r.marks.forEach((m) => { init[m.mark_id] = true; });
      setApprovals(init);
    },
  });

  const generateMut = useMutation({
    mutationFn: () => apiPost<DerivativeInfo>(`/documents/${docId}/redactions`, {
      approvals: (analyzeMut.data?.marks ?? []).map((m) => ({ mark_id: m.mark_id, approved: approvals[m.mark_id] ?? false })),
      reason: reason.trim(),
    }),
    onSuccess: (r) => {
      setResult(r);
      derivQuery.refetch();
    },
  });

  const marks = analyzeMut.data?.marks ?? [];
  const approvedCount = marks.filter((m) => approvals[m.mark_id]).length;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div style={{ fontFamily: 'var(--mono)', color: 'var(--amber)', fontSize: 13, letterSpacing: 1 }}>
            {docQuery.data?.title ?? '…'}
          </div>
          <h1>✏️ Redaction review</h1>
          <p className="sub">
            Approve or reject each proposed PII mark, then burn the approved marks into a new derivative version.
            The original bytes are never touched.
          </p>
        </div>
        <Link className="btn" to={`/cases/${caseId}`}>← Back to case</Link>
      </div>

      {docQuery.isLoading && <Spinner label="Loading document…" />}
      {docQuery.error && <ErrorBanner error={docQuery.error} />}

      {docQuery.data && (
        <>
          {!analyzeMut.data && !analyzeMut.isPending && (
            <div className="card mb">
              <h3>Step 1 — Analyze</h3>
              <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
                Run the rules-based detector over the extracted text (Aadhaar-like numbers, Indian phone numbers, email addresses).
              </p>
              <button type="button" className="btn btn-primary" onClick={() => analyzeMut.mutate()}>
                🔎 Analyze for PII
              </button>
            </div>
          )}
          {analyzeMut.isPending && <Spinner label="Analyzing document text…" />}
          {analyzeMut.error && <ErrorBanner error={analyzeMut.error} onRetry={() => analyzeMut.mutate()} />}

          {analyzeMut.data && !result && (
            <>
              <div className="section-title">Step 2 — Review proposed marks ({marks.length})</div>
              {marks.length === 0 && <Empty icon="🔎" title="No PII found" hint="The analyzer proposed no marks for this document." />}
              {marks.map((m) => (
                <div key={m.mark_id} className="mark-card">
                  <label className="checkbox-row" style={{ alignItems: 'flex-start', paddingTop: 4 }}>
                    <input
                      type="checkbox"
                      checked={approvals[m.mark_id] ?? false}
                      onChange={(e) => setApprovals((a) => ({ ...a, [m.mark_id]: e.target.checked }))}
                      aria-label={`Approve mark ${m.label} on page ${m.page}`}
                    />
                  </label>
                  <div className="grow">
                    <div className="row wrap" style={{ gap: 8 }}>
                      <span className={`pill ${LABEL_PILL[m.label] ?? 'pill-gray'}`}>{m.label}</span>
                      <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>page {m.page}</span>
                    </div>
                    <div className="conf" style={{ maxWidth: 260, marginTop: 8 }}>
                      <span style={{ fontSize: 12, color: 'var(--muted)' }}>confidence {(m.confidence * 100).toFixed(0)}%</span>
                      <div className="conf-bar"><div style={{ width: `${Math.round(m.confidence * 100)}%` }} /></div>
                    </div>
                    <div className="mark-excerpt">“{m.text_excerpt}”</div>
                  </div>
                </div>
              ))}

              {marks.length > 0 && (
                <div className="card mt">
                  <h3>Step 3 — Generate redacted derivative</h3>
                  <p style={{ color: 'var(--muted)', fontSize: 13.5 }}>
                    {approvedCount} of {marks.length} marks approved. Approved marks are burned in as black overlays
                    with the underlying text stripped. Requires a reason for the audit trail.
                    <br />Only Legal Reviewers and Custodians may approve (backend-enforced).
                  </p>
                  <ReasonField value={reason} onChange={setReason} required />
                  {generateMut.error && <ErrorBanner error={generateMut.error} />}
                  <button type="button" className="btn btn-primary btn-lg" disabled={!reason.trim() || generateMut.isPending}
                    onClick={() => generateMut.mutate()}>
                    {generateMut.isPending ? <><span className="spinner" /> Rendering…</> : `🧬 Generate redacted derivative (${approvedCount} marks)`}
                  </button>
                </div>
              )}
            </>
          )}

          {result && (
            <div className="mt">
              <div className="banner banner-ok">
                <span className="icon">🧬</span>
                <div className="grow">
                  <strong>Redacted derivative created — v{result.version_number}</strong>
                  <div>Approved marks burned in as black overlays. The original version is untouched and still sealed.</div>
                </div>
              </div>
              <div className="compare">
                <div className="card">
                  <h3>📄 Original (untouched)</h3>
                  <dl className="kv">
                    <dt>Version</dt><dd>v{docQuery.data.current_version.version_number}</dd>
                    <dt>Size</dt><dd>{formatBytes(docQuery.data.current_version.size_bytes)}</dd>
                    <dt>Created</dt><dd>{formatTs(docQuery.data.current_version.created_at)}</dd>
                  </dl>
                  <div className="hash-block"><span className="lbl">SHA-256</span><Hash value={docQuery.data.current_version.sha256} /></div>
                </div>
                <div className="card" style={{ borderColor: 'rgba(52, 211, 153, 0.4)' }}>
                  <h3>🧬 Derivative (redacted)</h3>
                  <dl className="kv">
                    <dt>Version</dt><dd>v{result.version_number}</dd>
                    <dt>Parent</dt><dd>v{docQuery.data.current_version.version_number} — linked</dd>
                    <dt>Marks burned</dt><dd>{approvedCount}</dd>
                  </dl>
                  <div className="hash-block"><span className="lbl">SHA-256</span><Hash value={result.sha256} /></div>
                </div>
              </div>
              <div className="banner banner-info">
                <span className="icon">🔒</span>
                <div><strong>Original bytes untouched</strong><div>The derivative is a new version with a parent link — the sealed original still verifies against its recorded hash.</div></div>
              </div>
              <button type="button" className="btn btn-ghost" onClick={() => { setResult(null); setReason(''); }}>
                ← Review another round
              </button>
            </div>
          )}

          {derivQuery.data && derivQuery.data.length > 0 && !result && (
            <div className="mt">
              <div className="section-title">Existing derivatives</div>
              {derivQuery.data.map((d) => (
                <div key={d.id} className="card flat" style={{ marginBottom: 10, padding: 12 }}>
                  <div className="row"><strong>v{d.version_number}</strong><span className="pill pill-violet">derivative</span>
                    <span className="grow" /><span style={{ color: 'var(--faint)', fontSize: 12 }}>{formatTs(d.created_at)}</span></div>
                  <div className="mt"><Hash value={d.sha256} short={32} /></div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
