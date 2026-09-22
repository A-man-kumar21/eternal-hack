import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import type { AuditEvent, CaseDetail, ChainVerifyResult } from '../api/types';
import { Empty, ErrorBanner, Hash, Spinner, Trunc, formatTs } from '../components/ui';

const OUTCOME_PILL: Record<string, string> = {
  ALLOWED: 'pill-green', DENIED: 'pill-red', FAILED: 'pill-red', INCIDENT: 'pill-amber',
};

function outcomePill(o: string) {
  return <span className={`pill ${OUTCOME_PILL[o] ?? 'pill-gray'}`}>{o}</span>;
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
    <div className="page">
      <div className="page-head">
        <div>
          <h1>🛡️ Auditor Console</h1>
          <p className="sub">
            High-signal security events and the tamper-evident audit log. Alert feed refreshes every 5 seconds.
            <span className="pill pill-amber" style={{ marginLeft: 10 }}>Auditors see all cases — backend enforces access</span>
          </p>
        </div>
      </div>

      <div className="section-title">🚨 Alert feed — DENIED · INCIDENT · FAILED</div>
      {alertsQuery.isLoading && <Spinner label="Loading alerts…" />}
      {alertsQuery.error && <ErrorBanner error={alertsQuery.error} onRetry={() => alertsQuery.refetch()} />}
      {!alertsQuery.isLoading && !alertsQuery.error && alerts.length === 0 && (
        <Empty icon="✅" title="No alerts" hint="No denied authorizations, incidents or failures. The feed polls every 5s." />
      )}
      {alerts.map((a) => (
        <div key={a.id} className={`card alert-card mb ${a.outcome === 'DENIED' ? 'denied' : a.outcome === 'INCIDENT' ? 'incident' : ''}`} style={{ padding: 14 }}>
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
        </div>
      ))}

      <div className="section-title">📜 Audit log & chain verification</div>
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
        {chain && (
          <div className={`banner ${chain.ok ? 'banner-ok' : 'banner-error'}`} style={{ marginBottom: 0 }}>
            <span className="icon">{chain.ok ? '✅' : '⛔'}</span>
            <div>
              <strong>{chain.ok ? 'CHAIN OK — hash links intact' : 'CHAIN BROKEN — tampering detected'}</strong>
              <div>{chain.events_checked} events checked, every <code style={{ fontFamily: 'var(--mono)' }}>prev_hash → event_hash</code> link recomputed.</div>
              {!chain.ok && chain.broken_at_id && <div className="rid">Broken at event: {chain.broken_at_id}</div>}
            </div>
          </div>
        )}
      </div>

      {!caseId && <Empty icon="📜" title="Select a case" hint="Pick a case above to read its audit events." />}
      {auditQuery.isLoading && <Spinner label="Loading audit events…" />}
      {auditQuery.error && <ErrorBanner error={auditQuery.error} onRetry={() => auditQuery.refetch()} />}
      {auditQuery.data && (
        <div className="table-wrap">
          <table className="tbl">
            <thead>
              <tr>
                <th>Time</th><th>Actor</th><th>Action</th><th>Object</th><th>Outcome</th><th>Reason</th><th>Request ID</th>
              </tr>
            </thead>
            <tbody>
              {auditQuery.data.map((e) => (
                <tr key={e.id}>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12, whiteSpace: 'nowrap' }}>{formatTs(e.created_at)}</td>
                  <td><Trunc text={e.actor_name ?? e.actor_id} max={18} /></td>
                  <td><Trunc text={e.action} max={28} /></td>
                  <td><Trunc text={e.object_id} max={14} /></td>
                  <td>{outcomePill(e.outcome)}</td>
                  <td><Trunc text={e.reason} max={36} /></td>
                  <td>{e.request_id ? <Hash value={e.request_id} short={10} /> : <span style={{ color: 'var(--faint)' }}>—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {auditQuery.data && auditQuery.data.length === 0 && (
        <Empty icon="📜" title="No audit events" hint="Nothing has happened on this case yet." />
      )}
    </div>
  );
}
