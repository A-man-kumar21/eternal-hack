import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiGet, apiPost } from '../api/client';
import type { CaseDetail } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Empty, ErrorBanner, Modal, SkeletonCards } from '../components/ui';
import { Item, Lift, Page, Stagger } from '../components/motion';

export default function Cases() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['cases'],
    queryFn: () => apiGet<CaseDetail[]>('/cases'),
  });

  if (isLoading) {
    return (
      <Page>
        <div className="page-head">
          <div>
            <div className="eyebrow">Evidence lockers</div>
            <h1>Case files</h1>
          </div>
        </div>
        <SkeletonCards count={6} />
      </Page>
    );
  }

  const totalDocs = (data ?? []).reduce((n, c) => n + (c.document_count ?? 0), 0);
  const totalMembers = (data ?? []).reduce((n, c) => n + c.members.length, 0);

  return (
    <Page>
      <div className="page-head">
        <div>
          <div className="eyebrow">Evidence lockers</div>
          <h1>Case files</h1>
          <p className="sub">Every case is a sealed evidence locker — documents, custody chain, audit trail and exports live inside.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setShowNew(true)}>＋ New case</button>
      </div>

      {error && <ErrorBanner error={error} onRetry={() => refetch()} />}

      {!error && data && data.length > 0 && (
        <Stagger className="stat-grid">
          <Item className="card stat-card">
            <div className="lbl">📁 Open cases</div>
            <div className="val amber">{data.length}</div>
          </Item>
          <Item className="card stat-card">
            <div className="lbl">📄 Documents sealed</div>
            <div className="val">{totalDocs}</div>
          </Item>
          <Item className="card stat-card">
            <div className="lbl">👥 Case members</div>
            <div className="val blue">{totalMembers}</div>
          </Item>
        </Stagger>
      )}

      {!error && data && data.length === 0 && (
        <Empty icon="📁" title="No cases yet" hint="Create your first case to start ingesting evidence."
          action={<button type="button" className="btn btn-primary" onClick={() => setShowNew(true)}>＋ New case</button>} />
      )}

      <Stagger className="card-grid">
        {data?.map((c) => {
          const myRole = c.members.find((m) => m.user_id === user?.id)?.role;
          return (
            <Item key={c.id}>
              <Lift
                className="card case-card"
                onClick={() => navigate(`/cases/${c.id}`)}
                role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/cases/${c.id}`); }}
              >
                <div className="num">{c.case_number}</div>
                <h3>{c.title}</h3>
                <div style={{ color: 'var(--muted)', fontSize: 13.5, lineHeight: 1.55 }}>{c.description || 'No description.'}</div>
                <div className="meta">
                  <span>📄 {c.document_count ?? '—'} docs</span>
                  <span>👥 {c.members.length} members</span>
                  {myRole && <span className="role-badge">{myRole.replace(/_/g, ' ')}</span>}
                </div>
              </Lift>
            </Item>
          );
        })}
      </Stagger>

      <NewCaseModal
        open={showNew}
        onClose={() => setShowNew(false)}
        onCreated={(id) => {
          setShowNew(false);
          qc.invalidateQueries({ queryKey: ['cases'] });
          navigate(`/cases/${id}`);
        }}
      />
    </Page>
  );
}

function NewCaseModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (id: string) => void }) {
  const [caseNumber, setCaseNumber] = useState('');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<{ msg: string; rid: string | null } | null>(null);

  const mut = useMutation({
    mutationFn: () => apiPost<CaseDetail>('/cases', { case_number: caseNumber.trim(), title: title.trim(), description: description.trim() || undefined }),
    onSuccess: (c) => onCreated(c.id),
    onError: (e) => {
      if (e instanceof ApiError) setError({ msg: e.friendly, rid: e.requestId });
      else setError({ msg: e instanceof Error ? e.message : 'Failed', rid: null });
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!caseNumber.trim() || !title.trim()) return;
    setError(null);
    mut.mutate();
  };

  return (
    <Modal open={open} title="New case" desc="You will be added as a member with your own role. Others can be added later from the workspace." onClose={onClose}>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="nc-num">Case number</label>
          <input id="nc-num" className="input" value={caseNumber} onChange={(e) => setCaseNumber(e.target.value)}
            placeholder="e.g. FIR/2026/0142" required />
        </div>
        <div className="field">
          <label htmlFor="nc-title">Title</label>
          <input id="nc-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Cyber-fraud ring — Andheri cluster" required />
        </div>
        <div className="field">
          <label htmlFor="nc-desc">Description</label>
          <textarea id="nc-desc" className="textarea" value={description} onChange={(e) => setDescription(e.target.value)}
            placeholder="Brief summary of the matter…" />
        </div>
        {error && (
          <div className="banner banner-error"><span className="icon">⚠️</span>
            <div><strong>Could not create case</strong><div>{error.msg}</div>
              {error.rid && <div className="rid">Request ID: {error.rid}</div>}</div></div>
        )}
        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={mut.isPending}>
            {mut.isPending ? <><span className="spinner" /> Creating…</> : 'Create case'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
