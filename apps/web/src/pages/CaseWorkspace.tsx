import { useEffect, useRef, useState } from 'react';
import type { DragEvent, FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'motion/react';
import { ApiError, apiBlob, apiGet, apiPost, apiPostForm } from '../api/client';
import { useCaseDocuments } from '../api/hooks';
import type {
  CaseDetail, CustodyEvent, Document, IngestResponse, RedactionMark, User, VerifyResult, Version,
} from '../api/types';
import { useAuth } from '../auth/AuthContext';
import {
  AvBadge, Empty, ErrorBanner, Hash, Modal, ReasonField, SkeletonRows, Spinner, StatusPill, formatBytes, formatTs,
} from '../components/ui';
import { EASE, FadeIn, Item, Page, Stagger, springSnappy } from '../components/motion';

const DOC_TYPES = ['FIR', 'EVIDENCE_PHOTO', 'CHARGE_SHEET', 'COURT_FILING', 'STATEMENT', 'OTHER'] as const;
const DOC_ICON: Record<string, string> = {
  FIR: '🚨', EVIDENCE_PHOTO: '📷', CHARGE_SHEET: '📜', COURT_FILING: '⚖️', STATEMENT: '🗣️', OTHER: '📄',
};

type Derivative = Version & { parent_version_id?: string; parent_version_number?: number };

async function downloadViaApi(path: string, query: Record<string, string | undefined>, fallback: string) {
  const { blob, filename } = await apiBlob(path, query);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || fallback;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export default function CaseWorkspace() {
  const { id: caseId = '' } = useParams();
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [showAddMember, setShowAddMember] = useState(false);

  const caseQuery = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => apiGet<CaseDetail>(`/cases/${caseId}`),
  });
  const docsQuery = useCaseDocuments(caseId);

  // Prune uploads that finished ingesting
  useEffect(() => {
    if (!docsQuery.data || pendingIds.length === 0) return;
    const still = pendingIds.filter((pid) => {
      const d = docsQuery.data!.find((x) => x.id === pid);
      return !d || d.status === 'INGESTING';
    });
    if (still.length !== pendingIds.length) setPendingIds(still);
  }, [docsQuery.data, pendingIds]);

  if (caseQuery.isLoading) return <Page><Spinner label="Opening case file…" /></Page>;
  if (caseQuery.error) return <Page><ErrorBanner error={caseQuery.error} onRetry={() => caseQuery.refetch()} /></Page>;

  const c = caseQuery.data!;

  return (
    <Page>
      <div className="page-head">
        <div>
          <div className="eyebrow">{c.case_number}</div>
          <h1>{c.title}</h1>
          <p className="sub">{c.description || 'No description.'}</p>
          <div className="row wrap mt" style={{ gap: 8 }}>
            {c.members.map((m, i) => (
              <motion.span
                key={m.user_id}
                className="chip"
                title={m.username}
                style={{ cursor: 'default' }}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.15 + i * 0.05, duration: 0.3, ease: EASE }}
              >
                {m.display_name} <small>{m.role.replace(/_/g, ' ')}</small>
              </motion.span>
            ))}
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setShowAddMember(true)}>＋ member</button>
          </div>
        </div>
        <div className="row wrap" style={{ justifyContent: 'flex-end' }}>
          <Link className="btn" to={`/cases/${caseId}/timeline`}>🕘 Timeline</Link>
          <Link className="btn" to={`/cases/${caseId}/export`}>📦 Export</Link>
        </div>
      </div>

      <FadeIn delay={0.1}>
        <UploadCard
          caseId={caseId}
          onUploaded={(docId) => {
            setPendingIds((p) => [...p, docId]);
            docsQuery.refetch();
          }}
        />
      </FadeIn>

      <div className="section-title">Documents {docsQuery.data ? `(${docsQuery.data.length})` : ''}</div>
      {docsQuery.isLoading && <SkeletonRows count={4} />}
      {docsQuery.error && <ErrorBanner error={docsQuery.error} onRetry={() => docsQuery.refetch()} />}
      {!docsQuery.isLoading && !docsQuery.error && docsQuery.data!.length === 0 && !pendingIds.length && (
        <Empty icon="📂" title="No documents yet" hint="Upload the first piece of evidence above — the ingest pipeline hashes, encrypts and stores it." />
      )}
      <AnimatePresence>
        {pendingIds.length > 0 && (
          <motion.div
            className="banner banner-info"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3, ease: EASE }}
          >
            <span className="icon"><span className="spinner" /></span>
            <div><strong>Ingest pipeline running…</strong>
              <div>{pendingIds.length} document{pendingIds.length > 1 ? 's' : ''} being hashed, encrypted and stored. This list refreshes automatically.</div></div>
          </motion.div>
        )}
      </AnimatePresence>
      <Stagger>
        {docsQuery.data?.map((d) => (
          <Item key={d.id}>
            <motion.div
              className={`doc-row ${selectedDoc === d.id ? 'selected' : ''}`}
              onClick={() => setSelectedDoc(d.id)}
              role="button" tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') setSelectedDoc(d.id); }}
              whileHover={{ x: 4 }}
              whileTap={{ scale: 0.995 }}
              transition={springSnappy}
              layout
            >
              <motion.span
                className="icon"
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 300, damping: 18 }}
              >
                {DOC_ICON[d.doc_type] ?? '📄'}
              </motion.span>
              <div className="grow">
                <div className="title">{d.title}</div>
                <div className="sub">{d.doc_type} · v{d.current_version.version_number} · <Hash value={d.current_version.sha256} short={12} /> · {d.version_count} versions</div>
                {d.status === 'QUARANTINED' && d.quarantine_reason && (
                  <div style={{ color: 'var(--red)', fontSize: 12.5, marginTop: 4 }}>⚠️ {d.quarantine_reason}</div>
                )}
              </div>
              <StatusPill status={d.status} />
            </motion.div>
          </Item>
        ))}
      </Stagger>

      <AnimatePresence>
        {selectedDoc && (
          <DocDrawer docId={selectedDoc} caseId={caseId} caseDetail={c} onClose={() => setSelectedDoc(null)} />
        )}
      </AnimatePresence>
      <AddMemberModal open={showAddMember} caseId={caseId} onClose={() => setShowAddMember(false)} />
    </Page>
  );
}

/* ---------------- upload ---------------- */

function UploadCard({ caseId, onUploaded }: { caseId: string; onUploaded: (docId: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [docType, setDocType] = useState<string>('EVIDENCE_PHOTO');
  const [description, setDescription] = useState('');
  const [reason, setReason] = useState('');
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<{ msg: string; rid: string | null } | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const mut = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append('file', file!);
      form.append('title', title.trim() || file!.name);
      form.append('doc_type', docType);
      if (description.trim()) form.append('description', description.trim());
      if (reason.trim()) form.append('reason', reason.trim());
      return apiPostForm<IngestResponse>(`/cases/${caseId}/documents`, form);
    },
    onSuccess: (res) => {
      setError(null);
      setOk(`“${title.trim() || file!.name}” accepted — ingest pipeline running.`);
      onUploaded(res.document_id);
      setFile(null); setTitle(''); setDescription(''); setReason('');
      if (inputRef.current) inputRef.current.value = '';
    },
    onError: (e) => {
      setOk(null);
      if (e instanceof ApiError) setError({ msg: e.friendly, rid: e.requestId });
      else setError({ msg: e instanceof Error ? e.message : 'Upload failed', rid: null });
    },
  });

  const pick = (f: File | null) => {
    setFile(f);
    if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '));
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files?.[0] ?? null);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!file || mut.isPending) return;
    mut.mutate();
  };

  return (
    <div className="card">
      <h3>📥 Ingest evidence</h3>
      <form onSubmit={submit}>
        <motion.div
          className={`dropzone ${dragging ? 'dragging' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          animate={dragging ? { scale: 1.015, borderColor: '#f5a623' } : { scale: 1 }}
          transition={springSnappy}
        >
          <motion.div
            className="big"
            key={file ? file.name : 'empty'}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: EASE }}
          >
            {file ? `📄 ${file.name}` : 'Drop a file here or click to browse'}
          </motion.div>
          <div className="small">pdf · jpg · jpeg · png · txt — up to 25 MB. Pipeline: allowlist → size → MIME sniff → SHA-256 → AES-256-GCM encrypt → store.</div>
          <input ref={inputRef} type="file" hidden onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        </motion.div>
        <div className="compare">
          <div className="field">
            <label htmlFor="up-title">Title</label>
            <input id="up-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Document title" />
          </div>
          <div className="field">
            <label htmlFor="up-type">Document type</label>
            <select id="up-type" className="select" value={docType} onChange={(e) => setDocType(e.target.value)}>
              {DOC_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="up-desc">Description (optional)</label>
          <input id="up-desc" className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What is this document?" />
        </div>
        <ReasonField value={reason} onChange={setReason} />
        <AnimatePresence>
          {error && (
            <motion.div
              key="err"
              className="banner banner-error"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: EASE }}
            >
              <span className="icon">⚠️</span>
              <div><strong>Upload rejected</strong><div>{error.msg}</div>
                {error.rid && <div className="rid">Request ID: {error.rid}</div>}</div>
            </motion.div>
          )}
          {ok && (
            <motion.div
              key="ok"
              className="banner banner-ok"
              initial={{ opacity: 0, y: -8, scale: 0.99 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3, ease: EASE }}
            >
              <span className="icon">✅</span><div><strong>Accepted</strong><div>{ok}</div></div>
            </motion.div>
          )}
        </AnimatePresence>
        <button type="submit" className="btn btn-primary" disabled={!file || mut.isPending}>
          {mut.isPending ? <><span className="spinner" /> Uploading…</> : 'Upload & start pipeline'}
        </button>
      </form>
    </div>
  );
}

/* ---------------- document drawer ---------------- */

function DocDrawer({ docId, caseId, caseDetail, onClose }: { docId: string; caseId: string; caseDetail: CaseDetail; onClose: () => void }) {
  const [tab, setTab] = useState<'overview' | 'redactions' | 'derivatives'>('overview');
  const query = useQuery({
    queryKey: ['document', docId],
    queryFn: () => apiGet<Document>(`/documents/${docId}`),
    refetchInterval: (q) => {
      const d = q.state.data as Document | undefined;
      return d?.status === 'INGESTING' ? 2000 : false;
    },
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <>
      <motion.div
        className="drawer-overlay"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.22 }}
      />
      <motion.aside
        className="drawer"
        aria-label="Document detail"
        initial={{ x: 90, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 60, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 340, damping: 34 }}
      >
        <div className="drawer-head">
          <div>
            {query.data && <StatusPill status={query.data.status} />}
            <h2 style={{ margin: '8px 0 4px' }}>{query.data?.title ?? '…'}</h2>
            {query.data && <div style={{ color: 'var(--muted)', fontSize: 13 }}>{query.data.doc_type.replace(/_/g, ' ')} · ingested {formatTs(query.data.created_at)}</div>}
          </div>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onClose}>✕ Close</button>
        </div>

        {query.isLoading && <Spinner label="Loading document…" />}
        {query.error && <ErrorBanner error={query.error} onRetry={() => query.refetch()} />}

        {query.data && (
          <>
            <div className="tabs">
              {(['overview', 'redactions', 'derivatives'] as const).map((t) => (
                <button key={t} type="button" className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
                  {t[0].toUpperCase() + t.slice(1)}
                  {tab === t && (
                    <motion.span
                      className="tab-ink"
                      layoutId="drawer-tab-ink"
                      transition={{ type: 'spring', stiffness: 480, damping: 38 }}
                    />
                  )}
                </button>
              ))}
            </div>
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={tab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.22, ease: EASE }}
              >
                {tab === 'overview' && <OverviewTab doc={query.data} caseDetail={caseDetail} />}
                {tab === 'redactions' && <RedactionsTab doc={query.data} caseId={caseId} />}
                {tab === 'derivatives' && <DerivativesTab doc={query.data} />}
              </motion.div>
            </AnimatePresence>
          </>
        )}
      </motion.aside>
    </>
  );
}

function OverviewTab({ doc, caseDetail }: { doc: Document; caseDetail: CaseDetail }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);
  const [showCustody, setShowCustody] = useState(false);
  const [showFreeze, setShowFreeze] = useState(false);
  const [showDownload, setShowDownload] = useState(false);
  const [tamperState, setTamperState] = useState<'idle' | 'armed' | 'done' | 'unavailable'>('idle');

  const v = doc.current_version;
  const canFreeze = user?.role === 'EVIDENCE_CUSTODIAN';

  const verifyMut = useMutation({
    mutationFn: () => apiPost<VerifyResult>(`/documents/${doc.id}/verify`),
    onSuccess: (r) => {
      setVerifyResult(r);
      qc.invalidateQueries({ queryKey: ['case-documents', doc.case_id] });
    },
  });

  const freezeMut = useMutation({
    mutationFn: (reason: string) => apiPost(`/documents/${doc.id}/freeze`, { reason }),
    onSuccess: () => {
      setShowFreeze(false);
      qc.invalidateQueries({ queryKey: ['document', doc.id] });
      qc.invalidateQueries({ queryKey: ['case-documents', doc.case_id] });
      qc.invalidateQueries({ queryKey: ['timeline', doc.case_id] });
    },
  });

  const tamper = async () => {
    if (tamperState === 'idle') { setTamperState('armed'); return; }
    try {
      await apiPost(`/dev/corrupt-blob/${v.id}`);
      setTamperState('done');
    } catch {
      setTamperState('unavailable');
    }
  };

  return (
    <div>
      <dl className="kv">
        <dt>Title</dt><dd>{doc.title}</dd>
        <dt>Type</dt><dd>{doc.doc_type.replace(/_/g, ' ')}</dd>
        <dt>Status</dt><dd><StatusPill status={doc.status} /></dd>
        <dt>Antivirus</dt><dd><AvBadge status={v.av_status} detail={v.av_detail} /></dd>
        <dt>Version</dt><dd>v{v.version_number} of {doc.version_count}</dd>
        <dt>Size</dt><dd>{formatBytes(v.size_bytes)} · {v.mime_type}</dd>
        <dt>Created</dt><dd>{formatTs(doc.created_at)}</dd>
        {doc.description && <><dt>Description</dt><dd>{doc.description}</dd></>}
        {doc.quarantine_reason && <><dt>Quarantine</dt><dd style={{ color: 'var(--red)' }}>{doc.quarantine_reason}</dd></>}
      </dl>

      <div className="hash-block">
        <span className="lbl">SHA-256 (stored)</span>
        <Hash value={v.sha256} />
      </div>

      <div className="section-title">Integrity</div>
      <div className="row wrap">
        <button type="button" className="btn" onClick={() => verifyMut.mutate()} disabled={verifyMut.isPending || doc.status === 'INGESTING'}>
          {verifyMut.isPending ? <><span className="spinner" /> Verifying…</> : '🔍 Verify integrity'}
        </button>
        <button
          type="button" className="btn btn-sm btn-ghost" title="Dev-only: flips one byte in stored ciphertext (EABHILEKH_ENV=dev)"
          onClick={() => void tamper()} style={{ color: 'var(--faint)' }}>
          {tamperState === 'armed' ? '⚠️ Click again to confirm tamper' : '⚗️ Demo: simulate tamper'}
        </button>
      </div>
      <AnimatePresence>
        {tamperState === 'done' && (
          <motion.div key="t-done" className="banner banner-warn"
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            <span className="icon">⚗️</span>
            <div><strong>Stored blob tampered (demo)</strong><div>One byte of ciphertext was flipped. Run <em>Verify integrity</em> to see the failure.</div></div>
          </motion.div>
        )}
        {tamperState === 'unavailable' && (
          <motion.div key="t-un" className="banner banner-info"
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            <span className="icon">ℹ️</span>
            <div><strong>Dev endpoint unavailable</strong><div><code style={{ fontFamily: 'var(--mono)' }}>/dev/corrupt-blob</code> only works when the backend runs with <code style={{ fontFamily: 'var(--mono)' }}>EABHILEKH_ENV=dev</code>.</div></div>
          </motion.div>
        )}
      </AnimatePresence>
      {verifyMut.error && <ErrorBanner error={verifyMut.error} />}
      <AnimatePresence>
        {verifyResult && verifyResult.match && (
          <motion.div key="v-ok" className="banner banner-ok"
            initial={{ opacity: 0, scale: 0.98, y: -6 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}>
            <span className="icon">✅</span>
            <div className="grow"><strong>INTEGRITY VERIFIED — hashes match</strong>
              <div className="hash-block"><span className="lbl">Stored</span><Hash value={verifyResult.stored_sha256} /></div>
              <div className="hash-block"><span className="lbl">Computed</span><Hash value={verifyResult.computed_sha256} /></div>
              <div style={{ color: 'var(--muted)', fontSize: 12.5, marginTop: 6 }}>Verified at {formatTs(verifyResult.verified_at)} · version v{v.version_number}</div>
            </div>
          </motion.div>
        )}
        {verifyResult && !verifyResult.match && (
          <motion.div key="v-fail" className="integrity-fail" role="alert"
            initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 22 }}>
            <h2>⛔ INTEGRITY FAILURE</h2>
            <p><strong>Hash mismatch</strong> — the stored bytes no longer match the recorded SHA-256.</p>
            <div className="hash-block" style={{ textAlign: 'left' }}><span className="lbl">Stored</span><Hash value={verifyResult.stored_sha256} /></div>
            <div className="hash-block" style={{ textAlign: 'left' }}><span className="lbl">Computed</span><Hash value={verifyResult.computed_sha256} /></div>
            <p style={{ marginTop: 10 }}>🚨 An <strong>INCIDENT</strong> audit event has been logged and surfaced in the Auditor Console.</p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="section-title">Actions</div>
      <div className="row wrap">
        <button type="button" className="btn" onClick={() => { setDlError(null); setShowDownload(true); }}>⬇️ Download</button>
        <button type="button" className="btn" onClick={() => setShowCustody(true)}>🔄 Custody handoff</button>
        <button type="button" className="btn btn-danger" disabled={!canFreeze || doc.status === 'FROZEN'}
          title={canFreeze ? 'Freeze this document' : 'Only an Evidence Custodian can freeze'}
          onClick={() => setShowFreeze(true)}>
          ❄️ {doc.status === 'FROZEN' ? 'Frozen' : 'Freeze'}
        </button>
      </div>
      {!canFreeze && <div style={{ color: 'var(--faint)', fontSize: 12.5, marginTop: 8 }}>Freeze is restricted to Evidence Custodians (you are {user?.role.replace(/_/g, ' ')}).</div>}
      {dlError && <div className="banner banner-error"><span className="icon">⚠️</span><div><strong>Download failed</strong><div>{dlError}</div></div></div>}

      <div className="section-title">Versions</div>
      <VersionsList docId={doc.id} />

      <DownloadModal open={showDownload} doc={doc} onClose={() => setShowDownload(false)} onError={(m) => setDlError(m)} />
      <CustodyModal open={showCustody} doc={doc} caseDetail={caseDetail} onClose={() => setShowCustody(false)} />
      <ReasonActionModal
        open={showFreeze}
        title="Freeze document"
        desc="Frozen documents are sealed — no further changes until a custodian unfreezes (backend-enforced). A reason is required."
        confirmLabel="Freeze"
        danger
        busy={freezeMut.isPending}
        error={freezeMut.error}
        onClose={() => setShowFreeze(false)}
        onConfirm={(reason) => freezeMut.mutate(reason)}
      />
    </div>
  );
}

function VersionsList({ docId }: { docId: string }) {
  const q = useQuery({ queryKey: ['versions', docId], queryFn: () => apiGet<Version[]>(`/documents/${docId}/versions`) });
  if (q.isLoading) return <Spinner label="Loading versions…" />;
  if (q.error) return <ErrorBanner error={q.error} />;
  return (
    <Stagger>
      {q.data!.map((ver) => (
        <Item key={ver.id} className="card flat" style={{ marginBottom: 10, padding: 12 }}>
          <div className="row">
            <strong>v{ver.version_number}</strong>
            <AvBadge status={ver.av_status} detail={ver.av_detail} />
            <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>{formatBytes(ver.size_bytes)} · {ver.mime_type}</span>
            <span className="grow" />
            <span style={{ color: 'var(--faint)', fontSize: 12 }}>{formatTs(ver.created_at)}</span>
          </div>
          <div className="mt"><Hash value={ver.sha256} short={32} /></div>
        </Item>
      ))}
    </Stagger>
  );
}

function DownloadModal({ open, doc, onClose, onError }: { open: boolean; doc: Document; onClose: () => void; onError: (m: string) => void }) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const v = doc.current_version;

  const go = async () => {
    if (!reason.trim()) return;
    setBusy(true);
    try {
      await downloadViaApi(`/documents/${doc.id}/download`, { reason: reason.trim() }, `${doc.title || 'document'}`);
      onClose();
    } catch (e) {
      onError(e instanceof ApiError ? e.friendly : e instanceof Error ? e.message : 'Download failed');
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="Download original" desc="Downloading the original evidence file requires a reason — it is written to the audit trail. (Contract: reason required for originals.)" onClose={onClose}>
      <div className="hash-block"><span className="lbl">Version</span><span style={{ fontSize: 13.5 }}>v{v.version_number} · {formatBytes(v.size_bytes)}</span></div>
      <ReasonField value={reason} onChange={setReason} required />
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="button" className="btn btn-primary" disabled={!reason.trim() || busy} onClick={() => void go()}>
          {busy ? <><span className="spinner" /> Downloading…</> : '⬇️ Download'}
        </button>
      </div>
    </Modal>
  );
}

function CustodyModal({ open, doc, caseDetail, onClose }: { open: boolean; doc: Document; caseDetail: CaseDetail; onClose: () => void }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [action, setAction] = useState('handoff');
  const [toUser, setToUser] = useState('');
  const [reason, setReason] = useState('');

  const mut = useMutation({
    mutationFn: () => apiPost<CustodyEvent>(`/documents/${doc.id}/custody`, {
      action, to_user_id: toUser || undefined, reason: reason.trim(),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['timeline', doc.case_id] });
      onClose();
    },
  });

  const others = caseDetail.members.filter((m) => m.user_id !== user?.id);

  return (
    <Modal open={open} title="Custody event" desc="Record a chain-of-custody movement. The reason is stored on the audit event." onClose={onClose}>
      <div className="field">
        <label htmlFor="cu-action">Action</label>
        <select id="cu-action" className="select" value={action} onChange={(e) => setAction(e.target.value)}>
          <option value="handoff">handoff — transfer custody to another member</option>
          <option value="accept">accept — take custody</option>
          <option value="release">release — return to general custody</option>
        </select>
      </div>
      {action === 'handoff' && (
        <div className="field">
          <label htmlFor="cu-to">Hand off to</label>
          <select id="cu-to" className="select" value={toUser} onChange={(e) => setToUser(e.target.value)} required>
            <option value="" disabled>Select a case member…</option>
            {others.map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name} ({m.role.replace(/_/g, ' ')})</option>)}
          </select>
        </div>
      )}
      <ReasonField value={reason} onChange={setReason} required />
      {mut.error && <ErrorBanner error={mut.error} />}
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="button" className="btn btn-primary" disabled={!reason.trim() || (action === 'handoff' && !toUser) || mut.isPending}
          onClick={() => mut.mutate()}>
          {mut.isPending ? <><span className="spinner" /> Recording…</> : 'Record custody event'}
        </button>
      </div>
    </Modal>
  );
}

/** Generic "reason first, then confirm" modal for privileged/destructive actions. */
export function ReasonActionModal({ open, title, desc, confirmLabel, danger, busy, error, onClose, onConfirm }: {
  open: boolean; title: string; desc: string; confirmLabel: string; danger?: boolean; busy: boolean; error: unknown;
  onClose: () => void; onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  return (
    <Modal open={open} title={title} desc={desc} onClose={onClose}>
      <ReasonField value={reason} onChange={setReason} required />
      {error ? <ErrorBanner error={error} /> : null}
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="button" className={danger ? 'btn btn-danger' : 'btn btn-primary'}
          disabled={!reason.trim() || busy} onClick={() => onConfirm(reason.trim())}>
          {busy ? <><span className="spinner" /> Working…</> : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

function RedactionsTab({ doc, caseId }: { doc: Document; caseId: string }) {
  const [marks, setMarks] = useState<RedactionMark[] | null>(null);
  const mut = useMutation({
    mutationFn: () => apiPost<{ version_id: string; marks: RedactionMark[] }>(`/documents/${doc.id}/redactions/analyze`),
    onSuccess: (r) => setMarks(r.marks),
  });

  return (
    <div>
      <p style={{ color: 'var(--muted)', fontSize: 13.5, lineHeight: 1.55 }}>
        Rules-based PII detection (Aadhaar-like numbers, Indian phone numbers, emails; NER optional).
        Review and approve marks on the dedicated review page.
      </p>
      <div className="row wrap">
        <button type="button" className="btn" onClick={() => mut.mutate()} disabled={mut.isPending}>
          {mut.isPending ? <><span className="spinner" /> Analyzing…</> : '🔎 Analyze for PII'}
        </button>
        <Link className="btn btn-primary" to={`/cases/${caseId}/redact/${doc.id}`}>Open redaction review →</Link>
      </div>
      {mut.error && <ErrorBanner error={mut.error} />}
      <AnimatePresence>
        {marks && (
          <motion.div
            key="marks"
            className="mt"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35, ease: EASE }}
          >
            <div className="section-title">Proposed marks ({marks.length})</div>
            {marks.length === 0 && <Empty icon="🔎" title="No marks proposed" hint="The analyzer found no PII patterns in the extracted text." />}
            {marks.slice(0, 5).map((m) => (
              <div key={m.mark_id} className="mark-card">
                <div className="grow">
                  <span className="pill pill-violet">{m.label}</span>{' '}
                  <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>page {m.page} · {(m.confidence * 100).toFixed(0)}%</span>
                  <div className="mark-excerpt">{m.text_excerpt}</div>
                </div>
              </div>
            ))}
            {marks.length > 5 && <div style={{ color: 'var(--faint)', fontSize: 12.5 }}>…and {marks.length - 5} more — open the review page.</div>}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DerivativesTab({ doc }: { doc: Document }) {
  const q = useQuery({
    queryKey: ['derivatives', doc.id],
    queryFn: () => apiGet<Derivative[]>(`/documents/${doc.id}/derivatives`),
  });
  if (q.isLoading) return <Spinner label="Loading derivatives…" />;
  if (q.error) return <ErrorBanner error={q.error} />;
  if (q.data!.length === 0) return <Empty icon="🧬" title="No derivatives yet" hint="Generate a redacted derivative from the Redactions tab." />;
  return (
    <Stagger>
      {q.data!.map((d) => (
        <Item key={d.id} className="card flat" style={{ marginBottom: 10, padding: 12 }}>
          <div className="row">
            <strong>v{d.version_number}</strong>
            <span className="pill pill-violet">derivative</span>
            <span className="grow" />
            <span style={{ color: 'var(--faint)', fontSize: 12 }}>{formatTs(d.created_at)}</span>
          </div>
          <div className="mt"><Hash value={d.sha256} short={32} /></div>
          {(d.parent_version_id || d.parent_version_number !== undefined) && (
            <div style={{ color: 'var(--muted)', fontSize: 12.5, marginTop: 6 }}>
              ⬅ derived from {d.parent_version_number !== undefined ? `v${d.parent_version_number}` : 'parent version'} — original bytes untouched
            </div>
          )}
        </Item>
      ))}
    </Stagger>
  );
}

function AddMemberModal({ open, caseId, onClose }: { open: boolean; caseId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState('INVESTIGATOR');
  const usersQuery = useQuery({ queryKey: ['users'], queryFn: () => apiGet<User[]>('/users') });
  const mut = useMutation({
    mutationFn: () => apiPost(`/cases/${caseId}/members`, { user_id: userId, role }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['case', caseId] });
      onClose();
    },
  });

  return (
    <Modal open={open} title="Add case member" desc="Only investigators and custodians who are members may add members (backend-enforced)." onClose={onClose}>
      <div className="field">
        <label htmlFor="am-user">User</label>
        <select id="am-user" className="select" value={userId} onChange={(e) => setUserId(e.target.value)}>
          <option value="" disabled>{usersQuery.isLoading ? 'Loading…' : 'Select a user…'}</option>
          {usersQuery.data?.map((u) => <option key={u.id} value={u.id}>{u.display_name} ({u.username}) — {u.role.replace(/_/g, ' ')}</option>)}
        </select>
      </div>
      <div className="field">
        <label htmlFor="am-role">Role on this case</label>
        <select id="am-role" className="select" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="INVESTIGATOR">Investigator</option>
          <option value="LEGAL_REVIEWER">Legal Reviewer</option>
          <option value="EVIDENCE_CUSTODIAN">Evidence Custodian</option>
          <option value="SECURITY_AUDITOR">Security Auditor</option>
        </select>
      </div>
      {usersQuery.error && <ErrorBanner error={usersQuery.error} />}
      {mut.error && <ErrorBanner error={mut.error} />}
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button type="button" className="btn btn-primary" disabled={!userId || mut.isPending} onClick={() => mut.mutate()}>
          {mut.isPending ? <><span className="spinner" /> Adding…</> : 'Add member'}
        </button>
      </div>
    </Modal>
  );
}
