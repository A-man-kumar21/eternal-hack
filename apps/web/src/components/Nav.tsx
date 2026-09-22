import { useState } from 'react';
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import type { CaseDetail } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { RoleBadge } from './ui';

const DEMO_BEATS: Array<{ title: string; how: string }> = [
  { title: '1 · Ingest', how: 'Open a case → drop a file in the upload zone. Watch INGESTING pulse → ACTIVE as the pipeline hashes, encrypts and stores it.' },
  { title: '2 · Verify', how: 'Open the document drawer → “Verify integrity”. Stored vs computed SHA-256 — a green banner proves the bytes are intact.' },
  { title: '3 · Tampered copy', how: 'In the drawer, “Demo: simulate tamper” flips one byte in stored ciphertext (dev endpoint). Verify again → full-width red INTEGRITY FAILURE banner; an INCIDENT is logged to alerts.' },
  { title: '4 · Custody', how: '“Custody handoff” — pick an action, a recipient and a reason. Every move lands on the Timeline.' },
  { title: '5 · Redact', how: 'Redaction tab → Analyze → approve/reject proposed marks → “Generate redacted derivative”. A new burned-in version is linked to the untouched original.' },
  { title: '6 · Breach', how: 'Log out, sign in as outsider.mehta (chip below). Try to open a case you are not a member of → 403 DENIED, written to the audit log and surfaced in the Auditor Console.' },
  { title: '7 · Export', how: 'Export tab → select documents + reason → Build bundle. Download the ZIP with manifest.json, file hashes and the audit chain head.' },
];

function DemoGuide() {
  const [open, setOpen] = useState(false);
  return (
    <div className="popover-wrap">
      <button type="button" className="btn btn-sm btn-ghost" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        📋 Demo guide
      </button>
      {open && (
        <>
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 110 }}
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="popover" style={{ zIndex: 115 }}>
            <h3>Six-minute demo script</h3>
            <p style={{ color: 'var(--muted)', fontSize: 12.5, margin: '0 0 8px' }}>
              Follow the beats in order — each maps to one judging moment.
            </p>
            {DEMO_BEATS.map((b) => (
              <div className="beat" key={b.title}>
                <span className="n">{b.title.split(' ')[0]}</span>
                <div>
                  <strong>{b.title.split('· ')[1]}</strong>
                  <div style={{ color: 'var(--muted)', marginTop: 3 }}>{b.how}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function CaseSwitcher() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data } = useQuery({
    queryKey: ['cases'],
    queryFn: () => apiGet<CaseDetail[]>('/cases'),
  });
  if (!data || data.length === 0) return null;
  return (
    <label className="case-switcher">
      <select
        className="select"
        value={id ?? ''}
        onChange={(e) => { if (e.target.value) navigate(`/cases/${e.target.value}`); }}
        aria-label="Switch case"
      >
        <option value="" disabled>Switch case…</option>
        {data.map((c) => (
          <option key={c.id} value={c.id}>{c.case_number} — {c.title}</option>
        ))}
      </select>
    </label>
  );
}

export default function Nav() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <header className="topnav">
      <div className="topnav-inner">
        <Link to="/cases" className="brand">
          <span className="shield">🛡️</span>
          <span>e-Abhilekh<small>Evidence Console</small></span>
        </Link>
        <nav className="nav-links">
          <NavLink to="/cases" className={({ isActive }) => (isActive ? 'active' : '')}>Cases</NavLink>
          <NavLink to="/auditor" className={({ isActive }) => (isActive ? 'active' : '')}>Auditor Console</NavLink>
        </nav>
        <CaseSwitcher />
        <div className="nav-right">
          <DemoGuide />
          <RoleBadge role={user.role} />
          <span style={{ fontSize: 13.5, color: 'var(--muted)' }}>{user.display_name}</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={logout}>Logout</button>
        </div>
      </div>
    </header>
  );
}
