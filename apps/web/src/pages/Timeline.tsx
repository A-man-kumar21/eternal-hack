import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import type { CaseDetail, TimelineEvent, TimelineKind } from '../api/types';
import { Empty, ErrorBanner, Spinner, Trunc, formatTs } from '../components/ui';

const KINDS: TimelineKind[] = ['custody', 'audit', 'ingest', 'verify', 'redaction', 'export'];
const KIND_ICON: Record<TimelineKind, string> = {
  custody: '🔄', audit: '📝', ingest: '📥', verify: '✅', redaction: '✏️', export: '📦',
};
const KIND_PILL: Record<TimelineKind, string> = {
  custody: 'pill-blue', audit: 'pill-gray', ingest: 'pill-amber', verify: 'pill-green', redaction: 'pill-violet', export: 'pill-amber',
};

function outcomeOf(ev: TimelineEvent): string | null {
  const d = ev.detail;
  if (d && typeof d === 'object' && typeof (d as Record<string, unknown>).outcome === 'string') {
    return (d as Record<string, unknown>).outcome as string;
  }
  return null;
}

export default function Timeline() {
  const { id: caseId = '' } = useParams();
  const [kinds, setKinds] = useState<TimelineKind[]>(KINDS);
  const [playing, setPlaying] = useState(false);
  const [index, setIndex] = useState(0);
  const timer = useRef<number | null>(null);

  const caseQuery = useQuery({
    queryKey: ['case', caseId],
    queryFn: () => apiGet<CaseDetail>(`/cases/${caseId}`),
  });
  const tlQuery = useQuery({
    queryKey: ['timeline', caseId],
    queryFn: () => apiGet<{ events: TimelineEvent[] }>(`/cases/${caseId}/timeline`),
  });

  const events = useMemo(() => {
    const evs = (tlQuery.data?.events ?? []).filter((e) => kinds.includes(e.kind));
    return [...evs].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }, [tlQuery.data, kinds]);

  // Playback engine: step through events one by one
  useEffect(() => {
    if (!playing) return;
    if (index >= events.length - 1) {
      setPlaying(false);
      return;
    }
    timer.current = window.setTimeout(() => setIndex((i) => Math.min(i + 1, events.length - 1)), 1400);
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, [playing, index, events.length]);

  useEffect(() => {
    setIndex(0);
    setPlaying(false);
  }, [caseId, kinds.join(',')]);

  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);

  const toggleKind = (k: TimelineKind) =>
    setKinds((ks) => (ks.includes(k) ? ks.filter((x) => x !== k) : [...ks, k]));

  const start = () => {
    if (events.length === 0) return;
    setIndex(0);
    setPlaying(true);
  };

  const progress = events.length ? ((index + 1) / events.length) * 100 : 0;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div style={{ fontFamily: 'var(--mono)', color: 'var(--amber)', fontSize: 13, letterSpacing: 1 }}>
            {caseQuery.data?.case_number ?? '…'}
          </div>
          <h1>🕘 Custody timeline</h1>
          <p className="sub">Chronological chain-of-custody playback — every ingest, handoff, verification, redaction and export.</p>
        </div>
        <Link className="btn" to={`/cases/${caseId}`}>← Back to case</Link>
      </div>

      {tlQuery.error && <ErrorBanner error={tlQuery.error} onRetry={() => tlQuery.refetch()} />}
      {tlQuery.isLoading && <Spinner label="Loading timeline…" />}

      {!tlQuery.isLoading && !tlQuery.error && (
        <>
          <div className="card mb">
            <div className="row wrap" style={{ justifyContent: 'space-between' }}>
              <div className="row wrap">
                {!playing
                  ? <button type="button" className="btn btn-primary" onClick={start} disabled={events.length === 0}>▶ Play chain</button>
                  : <button type="button" className="btn" onClick={() => setPlaying(false)}>⏸ Pause</button>}
                {playing && <span style={{ color: 'var(--muted)', fontSize: 13.5 }}>Event {index + 1} of {events.length}</span>}
              </div>
              <div className="row wrap" style={{ gap: 14 }}>
                {KINDS.map((k) => (
                  <label key={k} className="checkbox-row" style={{ fontSize: 12.5 }}>
                    <input type="checkbox" checked={kinds.includes(k)} onChange={() => toggleKind(k)} />
                    <span className={`pill ${KIND_PILL[k]}`}>{KIND_ICON[k]} {k}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="progress" aria-label="Playback progress"><div style={{ width: `${progress}%` }} /></div>
          </div>

          {events.length === 0 && (
            <Empty icon="🕘" title="No events yet" hint="Ingest a document or record a custody event to start the chain." />
          )}

          {events.map((ev, i) => {
            const outcome = outcomeOf(ev);
            const cls = `tl-event ${playing && i === index ? 'playing' : ''} ${i < index || (!playing && false) ? 'played' : ''}`;
            return (
              <div key={ev.id} className={cls}>
                <div className="tic">{KIND_ICON[ev.kind] ?? '•'}</div>
                <div className="body">
                  <div className="row wrap" style={{ gap: 8 }}>
                    <span className={`pill ${KIND_PILL[ev.kind]}`}>{ev.kind}</span>
                    {outcome && (
                      <span className={`pill ${outcome === 'ALLOWED' ? 'pill-green' : outcome === 'DENIED' || outcome === 'INCIDENT' || outcome === 'FAILED' ? 'pill-red' : 'pill-gray'}`}>
                        {outcome}
                      </span>
                    )}
                  </div>
                  <div className="action mt" style={{ marginTop: 8 }}>{ev.action}</div>
                  <div className="meta">
                    👤 <Trunc text={ev.actor} /> · 🧾 <Trunc text={ev.object_id} max={24} />
                  </div>
                  {ev.reason && <div className="reason">“{ev.reason}”</div>}
                  {ev.detail && typeof ev.detail === 'string' && <div className="meta" style={{ marginTop: 6 }}>{ev.detail}</div>}
                </div>
                <div className="ts">{formatTs(ev.created_at)}</div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
