import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'motion/react';
import { apiGet } from '../api/client';
import type { AuditEvent, CaseDetail, ChainVerifyResult } from '../api/types';
import { Empty, ErrorBanner, Hash, SkeletonRows, Spinner, Trunc, formatTs } from '../components/ui';
import { EASE, FadeIn, Page, Reveal, springSnappy } from '../components/motion';

const OUTCOME_PILL: Record<string, string> = {
  ALLOWED: 'pill-green', DENIED: 'pill-red', FAILED: 'pill-red', INCIDENT: 'pill-amber',
};

function outcomePill(o: string) {
  return <span className={`pill ${OUTCOME_PILL[o] ?? 'pill-gray'}`}>{o}</span>;
}

/** Visual hash-linked chain: each block shows its hash chained to the previous.
 *  Before verification blocks render dimmed/pulsing; after verify each link
 *  gets a check, and a broken link lights up red. */
function ChainViz({ events, chain }: { events: AuditEvent[]; chain: ChainVerifyResult | null }) {
  const verified: boolean | null = chain ? chain.ok : null;
  const ordered = [...events].reverse(); // genesis first
  return (
    <div className={`chain-viz ${verified === false ? 'broken' : ''}`}>
      {ordered.map((e, i) => {
        const isBroken = chain?.broken_at_id != null && String(e.id) === String(chain.broken_at_id);
        return (
          <div
            key={e.id}
            className={`chain-block ${verified === null ? 'pending-verify' : ''} ${isBroken ? 'broken-link' : ''}`}
            style={{ animationDelay: `${Math.min(i * 70, 1400)}ms` }}
          >
            <div className="cb-head">
              <span className="cb-action">{e.action}</span>
              {verified === true && !isBroken && <span className="cb-check">✓ link ok</span>}
              {isBroken && <span style={{ color: 'var(--red)', fontWeight: 700 }}>✗ link broken here</span>}
              <span className="grow" />
              <span className="cb-meta">{e.actor_name ?? e.actor_id ?? '—'} · {formatTs(e.created_at)}</span>
            </div>
            <div className="cb-hash">
              hash <b><Trunc text={e.event_hash} max={22} /></b>
              {'  '}← prev <Trunc text={e.prev_hash} max={22} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function AuditorConsole() {
  const [caseId, setCaseId] = useState<string>('');
  const [chain, setChain] = useState<ChainVerifyResult | null>(null);

  const casesQuery = useQuery({
    queryKey: ['cases'],
    queryFn: () => apiGet<CaseDetail[]>('/cases'),
  });

  const alertsQuery = useQuery({
    queryKey: ['alerts'],
    queryFn: () => apiGet<{ alerts: AuditEvent[] }>('/alerts'),
    refetchInterval: 5000,
  });

  const auditQuery = useQuery({
    queryKey: ['audit', caseId],
    queryFn: () => apiGet<AuditEvent[]>(`/cases/${caseId}/audit`, { limit: 100 }),
    enabled: !!caseId,
  });

  const chainMut = useMutation({
    mutationFn: (cid: string) => apiGet<ChainVerifyResult>('/audit/verify-chain', { case_id: cid }),
    onSuccess: (r) => setChain(r),
  });

  const alerts = alertsQuery.data?.alerts ?? [];

  return (
    <Page>
      <div className="page-head">
        <div>
          <div className="eyebrow">Tamper-evident audit</div>
          <h1>🛡️ Auditor Console</h1>
          <p className="sub">
            High-signal security events and the tamper-evident audit log. Alert feed refreshes every 5 seconds.
            <span className="pill pill-amber" style={{ marginLeft: 10 }}>Auditors see all cases — backend enforces access</span>
          </p>
        </div>
      </div>

      <div className="section-title">🚨 Alert feed — DENIED · INCIDENT · FAILED</div>
      {alertsQuery.isLoading && <SkeletonRows count={3} />}
      {alertsQuery.error && <ErrorBanner error={alertsQuery.error} onRetry={() => alertsQuery.refetch()} />}
      {!alertsQuery.isLoading && !alertsQuery.error && alerts.length === 0 && (
        <Empty icon="✅" title="No alerts" hint="No denied authorizations, incidents or failures. The feed polls every 5s." />
      )}
      <motion.div layout>
        <AnimatePresence initial={false}>
          {alerts.map((a) => (
            <motion.div
              key={a.id}
              layout
              className={`card alert-card mb ${a.outcome === 'DENIED' ? 'denied' : a.outcome === 'INCIDENT' ? 'incident' : ''}`}
              style={{ padding: 14 }}
              initial={{ opacity: 0, y: -14, scale: 0.99 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={springSnappy}
            >
              <div className="row wrap" style={{ gap: 8 }}>
                {outcomePill(a.outcome)}
                <strong>{a.action}</strong>
                <span className="grow" />
                <span style={{ color: 'var(--faint)', fontSize: 12, fontFamily: 'var(--mono)' }}>{formatTs(a.created_at)}</span>
              </div>
              <div style={{ color: 'var(--muted)', fontSize: 13, marginTop: 8 }}>
                👤 {a.actor_name ?? a.actor_id ?? '—'}
                {a.case_id && <> · 📁 case <Trunc text={a.case_id} max={12} /></>}
                {a.object_id && <> · 🧾 <Trunc text={a.object_id} max={16} /></>}
              </div>
              {a.reason && <div style={{ marginTop: 8, fontSize: 13.5 }}>“{a.reason}”</div>}
              {a.request_id && (
                <div style={{ marginTop: 8 }}><span style={{ fontSize: 11.5, color: 'var(--faint)', marginRight: 8 }}>REQUEST ID</span><Hash value={a.request_id} short={18} /></div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      </motion.div>

      <div className="section-title">📜 Audit log & chain verification</div>
      <Reveal>
        <div className="card mb">
          <div className="row wrap">
            <div className="field grow" style={{ marginBottom: 0, minWidth: 240 }}>
              <label htmlFor="au-case">Case</label>
              <select id="au-case" className="select" value={caseId} onChange={(e) => { setCaseId(e.target.value); setChain(null); }}>
                <option value="" disabled>Select a case…</option>
                {casesQuery.data?.map((c) => <option key={c.id} value={c.id}>{c.case_number} — {c.title}</option>)}
              </select>
            </div>
            <button type="button" className="btn btn-primary" disabled={!caseId || chainMut.isPending}
              onClick={() => chainMut.mutate(caseId)} style={{ alignSelf: 'flex-end' }}>
              {chainMut.isPending ? <><span className="spinner" /> Verifying…</> : '🔗 Verify chain'}
            </button>
          </div>
          {chainMut.error && <ErrorBanner error={chainMut.error} />}
          <AnimatePresence>
            {chain && (
              <motion.div
                key={`chain-${chain.ok}`}
                className={`banner ${chain.ok ? 'banner-ok' : 'banner-error'}`}
                style={{ marginBottom: 0 }}
                initial={{ opacity: 0, scale: 0.98, y: -6 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ type: 'spring', stiffness: 320, damping: 26 }}
              >
                <span className="icon">{chain.ok ? '✅' : '⛔'}</span>
                <div>
                  <strong>{chain.ok ? 'CHAIN OK — hash links intact' : 'CHAIN BROKEN — tampering detected'}</strong>
                  <div>{chain.events_checked} events checked, every <code style={{ fontFamily: 'var(--mono)' }}>prev_hash → event_hash</code> link recomputed.</div>
                  {chain.last_anchored_hash && (
                    <div style={{ marginTop: 4 }}>
                      ⚓ Anchored checkpoint: <code style={{ fontFamily: 'var(--mono)' }}>{chain.last_anchored_hash.slice(0, 20)}…</code>{' '}
                      {chain.anchor_diverged
                        ? <strong style={{ color: 'var(--red)' }}>— history rewritten after anchor!</strong>
                        : <span style={{ color: 'var(--green)' }}>— matches, no rewrite</span>}
                    </div>
                  )}
                  {!chain.ok && chain.broken_at_id && <div className="rid">Broken at event: {chain.broken_at_id}</div>}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </Reveal>

      {auditQuery.data && auditQuery.data.length > 0 && (
        <>
          <div className="section-title">⛓️ Chain visualization — genesis → latest</div>
          <div className="card mb" style={{ padding: 18 }}>
            {!chain && (
              <div style={{ color: 'var(--muted)', fontSize: 13, marginBottom: 12 }}>
                Hit <strong>🔗 Verify chain</strong> above to light up every link — green means the
                hash chain recomputes cleanly end to end.
              </div>
            )}
            <ChainViz events={auditQuery.data} chain={chain} />
          </div>
        </>
      )}

      {!caseId && <Empty icon="📜" title="Select a case" hint="Pick a case above to read its audit events." />}
      {auditQuery.isLoading && <Spinner label="Loading audit events…" />}
      {auditQuery.error && <ErrorBanner error={auditQuery.error} onRetry={() => auditQuery.refetch()} />}
      {auditQuery.data && auditQuery.data.length > 0 && (
        <FadeIn>
          <div className="table-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Time</th><th>Actor</th><th>Action</th><th>Object</th><th>Outcome</th><th>Reason</th><th>Request ID</th>
                </tr>
              </thead>
              <tbody>
                {auditQuery.data.map((e, i) => (
                  <motion.tr
                    key={e.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: Math.min(i * 0.02, 0.4), duration: 0.3, ease: EASE }}
                  >
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 12, whiteSpace: 'nowrap' }}>{formatTs(e.created_at)}</td>
                    <td><Trunc text={e.actor_name ?? e.actor_id} max={18} /></td>
                    <td><Trunc text={e.action} max={28} /></td>
                    <td><Trunc text={e.object_id} max={14} /></td>
                    <td>{outcomePill(e.outcome)}</td>
                    <td><Trunc text={e.reason} max={36} /></td>
                    <td>{e.request_id ? <Hash value={e.request_id} short={10} /> : <span style={{ color: 'var(--faint)' }}>—</span>}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </FadeIn>
      )}
      {auditQuery.data && auditQuery.data.length === 0 && (
        <Empty icon="📜" title="No audit events" hint="Nothing has happened on this case yet." />
      )}
    </Page>
  );
}
