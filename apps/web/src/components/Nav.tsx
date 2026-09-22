import { useState } from 'react';
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'motion/react';
import { apiGet } from '../api/client';
import type { CaseDetail } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { RoleBadge } from './ui';
import { EASE } from './motion';

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
      <motion.button
        type="button"
        className="btn btn-sm btn-ghost"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        whileTap={{ scale: 0.95 }}
      >
        📋 Demo guide
      </motion.button>
      <AnimatePresence>
        {open && (
          <>
            <div
              style={{ position: 'fixed', inset: 0, zIndex: 110 }}
              onClick={() => setOpen(false)}
              aria-hidden
            />
            <motion.div
              className="popover"
              style={{ zIndex: 115 }}
              initial={{ opacity: 0, y: -8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.98 }}
              transition={{ duration: 0.22, ease: EASE }}
            >
              <h3>Six-minute demo script</h3>
              <p style={{ color: 'var(--muted)', fontSize: 12.5, margin: '0 0 8px' }}>
                Follow the beats in order — each maps to one judging moment.
              </p>
              {DEMO_BEATS.map((b, i) => (
                <motion.div
                  className="beat"
                  key={b.title}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.05 + i * 0.045, duration: 0.3, ease: EASE }}
                >
                  <span className="n">{b.title.split(' ')[0]}</span>
                  <div>
                    <strong>{b.title.split('· ')[1]}</strong>
                    <div style={{ color: 'var(--muted)', marginTop: 3 }}>{b.how}</div>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          </>
        )}
      </AnimatePresence>
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
    <motion.label
      className="case-switcher"
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, ease: EASE }}
    >
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
    </motion.label>
  );
}

function AnimatedNavLink({ to, label }: { to: string; label: string }) {
  return (
    <NavLink to={to} className={({ isActive }) => (isActive ? 'active' : '')}>
      {({ isActive }) => (
        <>
          {isActive && (
            <motion.span
              className="nav-pill-bg"
              layoutId="nav-active-pill"
              transition={{ type: 'spring', stiffness: 420, damping: 34 }}
            />
          )}
          <span className="nav-label">{label}</span>
        </>
      )}
    </NavLink>
  );
}

export default function Nav() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <motion.header
      className="topnav"
      initial={{ y: -56, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.45, ease: EASE }}
    >
      <div className="topnav-inner">
        <Link to="/dashboard" className="brand">
          <motion.span
            className="shield"
            whileHover={{ rotate: -8, scale: 1.08 }}
            whileTap={{ scale: 0.94 }}
            transition={{ type: 'spring', stiffness: 400, damping: 18 }}
          >
            🛡️
          </motion.span>
          <span>e-Abhilekh<small>Evidence Console</small></span>
        </Link>
        <nav className="nav-links">
          <AnimatedNavLink to="/dashboard" label="Dashboard" />
          <AnimatedNavLink to="/cases" label="Cases" />
          <AnimatedNavLink to="/auditor" label="Auditor Console" />
        </nav>
        <CaseSwitcher />
        <div className="nav-right">
          <DemoGuide />
          <RoleBadge role={user.role} />
          <span style={{ fontSize: 13.5, color: 'var(--muted)' }}>{user.display_name}</span>
          <motion.button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={logout}
            whileTap={{ scale: 0.95 }}
          >
            Logout
          </motion.button>
        </div>
      </div>
    </motion.header>
  );
}
