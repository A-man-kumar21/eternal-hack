import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'motion/react';
import { ApiError, apiBlob, apiGet, apiPost } from '../api/client';
import { useCaseDocuments } from '../api/hooks';
import type { CaseDetail, ExportBundle, ExportManifest } from '../api/types';
import { Empty, ErrorBanner, Hash, ReasonField, SkeletonRows, Trunc, formatTs } from '../components/ui';
import { EASE, FadeIn, Item, Page, Stagger } from '../components/motion';

export default function ExportPage() {
  const { id: caseId = '' } = useParams();
  const [selected, setSelected] = useState<string[]>([]);
  const [reason, setReason] = useState('');
  const [bundleId, setBundleId] = useState<string | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const caseQuery = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => apiGet<CaseDetail>(`/cases/${caseId}`),
  });
  const docsQuery = useCaseDocuments(caseId);

  const buildMut = useMutation({
    mutationFn: () => apiPost<{ bundle_id: string; status: string }>(`/cases/${caseId}/exports`, {
      document_ids: selected, reason: reason.trim(),
    }),
    onSuccess: (r) => setBundleId(r.bundle_id),
  });

  const bundleQuery = useQuery({
    queryKey: ['export-bundle', bundleId],
    queryFn: () => apiGet<ExportBundle>(`/exports/${bundleId}`),
    enabled: !!bundleId,
    refetchInterval: (q) => {
      const b = q.state.data as ExportBundle | undefined;
      return b && b.status !== 'ready' && b.status !== 'failed' ? 2000 : false;
    },
  });

  // Reset selection when the document list loads
  const docs = docsQuery.data;
  useEffect(() => {
    if (docs) setSelected((sel) => sel.filter((id) => docs.some((d) => d.id === id)));
  }, [docs]);

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const downloadZip = async () => {
    if (!bundleId) return;
    setDownloading(true);
    setDlError(null);
    try {
      const { blob, filename } = await apiBlob(`/exports/${bundleId}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || `e-abhilekh-bundle-${bundleId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch (e) {
      setDlError(e instanceof ApiError ? e.friendly : e instanceof Error ? e.message : 'Download failed');
    } finally {
      setDownloading(false);
    }
  };

  const bundle = bundleQuery.data;
  const manifest: ExportManifest | undefined = bundle?.manifest;
  const ready = bundle?.status === 'ready';
  const failed = bundle?.status === 'failed';

  return (
    <Page>
      <div className="page-head">
        <div>
          <div className="eyebrow">{caseQuery.data?.case_number ?? '…'}</div>
          <h1>📦 Export bundle</h1>
          <p className="sub">
            Build a sealed evidence bundle — decrypted files + <code style={{ fontFamily: 'var(--mono)' }}>manifest.json</code> with
            version hashes, custody summary and the audit chain head. Only Legal Reviewers and Custodians may export (backend-enforced).
          </p>
        </div>
        <Link className="btn" to={`/cases/${caseId}`}>← Back to case</Link>
      </div>

      {docsQuery.isLoading && <SkeletonRows count={4} />}
      {docsQuery.error && <ErrorBanner error={docsQuery.error} />}

      <AnimatePresence mode="wait" initial={false}>
        {!bundleId && docsQuery.data && (
          <motion.div
            key="select"
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25, ease: EASE }}
          >
            {docsQuery.data.length === 0 && (
              <Empty icon="📦" title="Nothing to export" hint="Ingest documents into this case first." />
            )}
            {docsQuery.data.length > 0 && (
              <FadeIn>
                <div className="card">
                  <h3>Select documents ({selected.length} selected)</h3>
                  <Stagger>
                    {docsQuery.data.map((d) => (
                      <Item key={d.id}>
                        <motion.label
                          className="checkbox-row"
                          style={{ padding: '10px 0', borderBottom: '1px solid var(--line-soft)', alignItems: 'flex-start' }}
                          whileTap={{ scale: 0.995 }}
                        >
                          <input type="checkbox" checked={selected.includes(d.id)} onChange={() => toggle(d.id)} disabled={d.status === 'QUARANTINED'} />
                          <div className="grow">
                            <div className="row wrap" style={{ gap: 8 }}>
                              <strong>{d.title}</strong>
                              <span className="pill pill-gray">v{d.current_version.version_number}</span>
                              {d.status === 'QUARANTINED' && <span className="pill pill-red">quarantined — excluded</span>}
                            </div>
                            <div style={{ marginTop: 4 }}><Hash value={d.current_version.sha256} short={24} /></div>
                          </div>
                        </motion.label>
                      </Item>
                    ))}
                  </Stagger>
                  <div className="mt">
                    <ReasonField value={reason} onChange={setReason} required />
                  </div>
                  {buildMut.error && <ErrorBanner error={buildMut.error} />}
                  <button type="button" className="btn btn-primary btn-lg"
                    disabled={selected.length === 0 || !reason.trim() || buildMut.isPending}
                    onClick={() => buildMut.mutate()}>
                    {buildMut.isPending ? <><span className="spinner" /> Building…</> : `📦 Build bundle (${selected.length})`}
                  </button>
                </div>
              </FadeIn>
            )}
          </motion.div>
        )}

        {bundleId && !ready && !failed && (
          <motion.div
            key="building"
            className="card"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.35, ease: EASE }}
          >
            <div className="loading-block">
              <span className="spinner" />
              Building bundle <code style={{ fontFamily: 'var(--mono)' }}>{bundleId}</code>… status: {bundle?.status ?? 'building'}
            </div>
            <div className="progress indeterminate"><div /></div>
            <div style={{ textAlign: 'center', color: 'var(--faint)', fontSize: 12.5, marginTop: 12 }}>
              Decrypting versions · writing manifest.json · sealing the audit chain head…
            </div>
          </motion.div>
        )}

        {failed && (
          <motion.div
            key="failed"
            className="banner banner-error"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: EASE }}
          >
            <span className="icon">⚠️</span>
            <div><strong>Bundle build failed</strong><div>The backend reported status <code style={{ fontFamily: 'var(--mono)' }}>failed</code>. Check the backend logs and try again.</div></div>
          </motion.div>
        )}

        {ready && bundle && (
          <motion.div
            key="ready"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.45, ease: EASE }}
          >
            <motion.div
              className="banner banner-ok"
              initial={{ scale: 0.98 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 24, delay: 0.1 }}
            >
              <span className="icon">📦</span>
              <div className="grow">
                <strong>Bundle ready — {manifest?.documents.length ?? '?'} documents sealed</strong>
                <div>Built {formatTs(bundle.created_at)} · contains files + manifest.json + README.txt</div>
              </div>
              <button type="button" className="btn btn-primary" onClick={() => void downloadZip()} disabled={downloading}>
                {downloading ? <><span className="spinner" /> Preparing…</> : '⬇️ Download ZIP'}
              </button>
            </motion.div>
            {dlError && <div className="banner banner-error"><span className="icon">⚠️</span><div><strong>Download failed</strong><div>{dlError}</div></div></div>}

            <div className="section-title">Manifest preview</div>
            <div className="card">
              <dl className="kv">
                <dt>Bundle ID</dt><dd><Hash value={bundle.id} short={18} /></dd>
                <dt>Case</dt><dd>{manifest?.case_number ?? caseQuery.data?.case_number}</dd>
                <dt>Exported by</dt><dd>{manifest?.exported_by ?? '—'} · {formatTs(manifest?.exported_at)}</dd>
                <dt>Bundle SHA-256</dt><dd>{bundle.sha256 ? <Hash value={bundle.sha256} /> : '—'}</dd>
                <dt>Audit chain head</dt><dd>{manifest?.audit_chain_head ? <Hash value={manifest.audit_chain_head} /> : '—'}</dd>
              </dl>
              <div className="table-wrap mt">
                <table className="tbl">
                  <thead><tr><th>Document</th><th>Type</th><th>Version</th><th>SHA-256</th><th>Custody events</th></tr></thead>
                  <tbody>
                    {manifest?.documents.map((m, i) => (
                      <motion.tr
                        key={m.document_id}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.15 + Math.min(i * 0.04, 0.4), duration: 0.3, ease: EASE }}
                      >
                        <td><Trunc text={m.title} max={30} /></td>
                        <td style={{ fontSize: 12 }}>{m.doc_type}</td>
                        <td>v{m.version_number}</td>
                        <td><Hash value={m.sha256} short={16} /></td>
                        <td style={{ fontSize: 12.5, color: 'var(--muted)' }}>{Array.isArray(m.custody) ? m.custody.length : '—'}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="mt">
              <button type="button" className="btn btn-ghost" onClick={() => { setBundleId(null); setReason(''); }}>
                ← Build another bundle
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Page>
  );
}
