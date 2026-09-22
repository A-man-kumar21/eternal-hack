import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiGet, apiPost } from '../api/client';
import type { AuditEvent, CaseDetail, ChainVerifyResult } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Empty, ErrorBanner, Spinner, formatTs } from '../components/ui';
import { Page } from '../components/motion';

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [resetMsg, setResetMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [resetting, setResetting] = useState(false);

  const casesQuery = useQuery({
    queryKey: ['cases'],
    queryFn: () => apiGet<CaseDetail[]>('/cases'),
  });
  const alertsQuery = useQuery({
    queryKey: ['alerts'],
    queryFn: () => apiGet<{ alerts: AuditEvent[] }>('/alerts'),
    refetchInterval: 10000,
  });

  const cases = casesQuery.data ?? [];
  const alerts = alertsQuery.data?.alerts ?? [];
  const firstCase = cases[0];

  const chainQuery = useQuery({
    queryKey: ['chain', firstCase?.id],
    queryFn: () => apiGet<ChainVerifyResult>('/audit/verify-chain', { case_id: firstCase!.id }),
    enabled: !!firstCase,
  });

  const docCount = cases.reduce((n, c) => n + (c.document_count ?? 0), 0);
  const chain: ChainVerifyResult | undefined = chainQuery.data;

  const resetDemo = async () => {
    setResetting(true);
    setResetMsg(null);
    try {
      await apiPost('/dev/reset', {});
      await qc.invalidateQueries();
      setResetMsg({ ok: true, text: 'Demo data reset — fresh fictional case, documents and audit trail loaded.' });
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setResetMsg({ ok: false, text: 'Reset is a dev-only endpoint — this backend was not started with EABHILEKH_ENV=dev.' });
      } else {
        setResetMsg({ ok: false, text: e instanceof Error ? e.message : 'Reset failed.' });
      }
    } finally {
      setResetting(false);
    }
  };

  const loading = casesQuery.isLoading || alertsQuery.isLoading;

  return (
    <Page>
      <div className="page-head">
        <div>
          <h1>Command deck</h1>
          <p className="sub">
            Welcome back, {user?.display_name}. Integrity posture across your cases at a glance —
            the numbers a judge asks for, before they ask.
          </p>
        </div>
      </div>

      {loading && <Spinner label="Loading command deck…" />}
      {casesQuery.error && <ErrorBanner error={casesQuery.error} onRetry={() => casesQuery.refetch()} />}

      {!loading && !casesQuery.error && (
        <>
          {firstCase && (
            <div className={`integrity-banner ${chain && !chain.ok ? 'broken' : ''}`}>
              <span className="big">{chainQuery.isLoading ? '⏳' : chain && !chain.ok ? '⛔' : '✅'}</span>
              <div>
                <strong>
                  {chainQuery.isLoading && 'Verifying audit chain…'}
                  {chain && chain.ok && `CHAIN VERIFIED — ${firstCase.case_number}`}
                  {chain && !chain.ok && `CHAIN BROKEN — ${firstCase.case_number}`}
                </strong>
                <div className="sub">
                  {chain
                    ? `${chain.events_checked} events re-hashed, every prev_hash → event_hash link recomputed.`
                    : 'Recomputing every hash link in the tamper-evident log.'}
                  {' '}<Link to="/auditor">Open Auditor Console →</Link>
                </div>
              </div>
            </div>
          )}

          <div className="stat-grid">
            <div className="card stat-card">
              <div className="k">Cases</div>
              <div className="v">{cases.length}</div>
            </div>
            <div className="card stat-card">
              <div className="k">Documents sealed</div>
              <div className="v">{docCount}</div>
            </div>
            <div className="card stat-card">
              <div className="k">Open alerts</div>
              <div className="v" style={alerts.length > 0 ? { color: 'var(--amber)' } : undefined}>{alerts.length}</div>
            </div>
            <div className="card stat-card">
              <div className="k">Audit chain</div>
              <div className="v">
                {chainQuery.isLoading ? <small>checking…</small>
                  : chain ? <small style={{ color: chain.ok ? 'var(--green)' : 'var(--red)' }}>{chain.ok ? 'VERIFIED' : 'BROKEN'}</small>
                  : <small>—</small>}
              </div>
            </div>
          </div>

          <div className="section-title">📁 Your cases</div>
          {cases.length === 0 && (
            <Empty icon="📁" title="No cases yet"
              hint="Load the fictional demo scenario to explore a full case instantly."
              action={<button type="button" className="btn btn-primary" onClick={resetDemo} disabled={resetting}>
                {resetting ? <><span className="spinner" /> Loading…</> : '🎬 Load demo scenario'}
              </button>} />
          )}
          <div className="card-grid">
            {cases.map((c) => (
              <div key={c.id} className="card case-card" onClick={() => navigate(`/cases/${c.id}`)} role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/cases/${c.id}`); }}>
                <div className="num">{c.case_number}</div>
                <h3>{c.title}</h3>
                <div style={{ color: 'var(--muted)', fontSize: 13.5 }}>{c.description || 'No description.'}</div>
                <div className="meta">
                  <span>📄 {c.document_count ?? '—'} docs</span>
                  <span>👥 {c.members.length} members</span>
                </div>
              </div>
            ))}
          </div>

          <div className="section-title">🚨 Latest alerts</div>
          {alerts.length === 0 && (
            <Empty icon="✅" title="All quiet" hint="Denials, incidents and failures will surface here within seconds." />
          )}
          {alerts.slice(0, 5).map((a) => (
            <div key={a.id} className="card mb" style={{ padding: 14 }}>
              <div className="row wrap" style={{ gap: 8 }}>
                <span className={`pill ${a.outcome === 'DENIED' ? 'pill-red' : 'pill-amber'}`}>{a.outcome}</span>
                <strong style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>{a.action}</strong>
                <span className="grow" />
                <span style={{ color: 'var(--faint)', fontSize: 12 }}>{formatTs(a.created_at)}</span>
              </div>
              {a.reason && <div style={{ color: 'var(--muted)', fontSize: 13, marginTop: 6 }}>“{a.reason}”</div>}
            </div>
          ))}

          <div className="section-title">🎬 Demo controls</div>
          <div className="card" style={{ padding: 18 }}>
            <div className="row wrap">
              <div className="grow" style={{ minWidth: 240 }}>
                <strong>Reset demo data</strong>
                <div style={{ color: 'var(--muted)', fontSize: 13, marginTop: 4 }}>
                  Wipes the database and reloads the fictional demo scenario — 5 users, a full case,
                  ingested documents, custody trail and redactions. Requires a dev backend.
                </div>
              </div>
              <button type="button" className="btn btn-ghost" onClick={resetDemo} disabled={resetting}>
                {resetting ? <><span className="spinner" /> Resetting…</> : '↺ Reset demo data'}
              </button>
            </div>
            {resetMsg && (
              <div className={`banner ${resetMsg.ok ? 'banner-ok' : 'banner-error'}`} style={{ marginBottom: 0, marginTop: 12 }}>
                <span className="icon">{resetMsg.ok ? '✅' : '⚠️'}</span>
                <div>{resetMsg.text}</div>
              </div>
            )}
          </div>
        </>
      )}
    </Page>
  );
}
