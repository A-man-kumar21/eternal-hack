import { useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { ApiError } from '../api/client';
import type { Role } from '../api/types';
import { ROLE_LABEL } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { EASE, staggerChild, staggerParent } from '../components/motion';

/** Fictional seeded demo accounts — per CONTRACT.md. Password for all: Demo@1234 */
const DEMO_USERS: Array<{ username: string; display_name: string; role: Role; note: string }> = [
  { username: 'inv.sharma', display_name: 'R. Sharma', role: 'INVESTIGATOR', note: 'uploads, custody handoff' },
  { username: 'leg.verma', display_name: 'S. Verma', role: 'LEGAL_REVIEWER', note: 'redaction review, export' },
  { username: 'cust.iyer', display_name: 'K. Iyer', role: 'EVIDENCE_CUSTODIAN', note: 'freeze, accept custody' },
  { username: 'aud.khan', display_name: 'F. Khan', role: 'SECURITY_AUDITOR', note: 'audit + alerts, all cases' },
  { username: 'outsider.mehta', display_name: 'J. Mehta', role: 'INVESTIGATOR', note: 'not a case member — breach demo' },
];

const DEMO_PASSWORD = 'Demo@1234';

const TRUST_POINTS = [
  { icon: '🔗', title: 'Hash-chained audit trail', text: 'Every action is append-only and tamper-evident — prev_hash → event_hash, verifiable end to end.' },
  { icon: '🔐', title: 'AES-256-GCM at rest', text: 'Evidence bytes are encrypted before storage. Integrity is re-verified on every read.' },
  { icon: '👥', title: 'Role-based custody', text: 'Investigators, reviewers, custodians and auditors each see exactly what the law allows.' },
];

function AnimatedShield() {
  return (
    <motion.svg
      width="72" height="72" viewBox="0 0 72 72" fill="none"
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: EASE }}
      style={{ marginBottom: 22 }}
    >
      <motion.path
        d="M36 6 L58 14 V34 C58 50 48 60 36 66 C24 60 14 50 14 34 V14 Z"
        stroke="#f5a623" strokeWidth="2.5" fill="rgba(245,166,35,0.08)"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1.4, ease: 'easeInOut', delay: 0.2 }}
      />
      <motion.path
        d="M27 36 L33 42 L46 28"
        stroke="#34d399" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.7, ease: 'easeOut', delay: 1.15 }}
      />
    </motion.svg>
  );
}

export default function Login() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<{ msg: string; rid: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && user) return <Navigate to="/dashboard" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) setError({ msg: err.friendly, rid: err.requestId });
      else setError({ msg: err instanceof Error ? err.message : 'Login failed', rid: null });
    } finally {
      setBusy(false);
    }
  };

  const quickFill = (u: string) => {
    setUsername(u);
    setPassword(DEMO_PASSWORD);
    setError(null);
  };

  return (
    <motion.div
      className="login-split"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, y: -12 }}
      transition={{ duration: 0.35, ease: EASE }}
    >
      {/* Brand panel */}
      <div className="login-side">
        <div className="login-grid-bg" />
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <motion.div
          className="login-side-inner"
          variants={staggerParent}
          initial="hidden"
          animate="show"
        >
          <AnimatedShield />
          <motion.div variants={staggerChild}>
            <span className="login-devanagari">अभिलेख</span>
          </motion.div>
          <motion.h1 className="brand-title" variants={staggerChild}>
            e-<span className="gold">Abhilekh</span>
          </motion.h1>
          <motion.p className="tagline" variants={staggerChild}>
            The sealed digital evidence locker for legal &amp; investigation records —
            FIRs, evidence, charge sheets and court filings, protected from ingest to courtroom.
          </motion.p>
          <div className="trust-list">
            {TRUST_POINTS.map((t) => (
              <motion.div className="trust-item" key={t.title} variants={staggerChild}>
                <span className="tic">{t.icon}</span>
                <div>
                  <strong>{t.title}</strong>
                  <p>{t.text}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Form panel */}
      <div className="login-form-col">
        <motion.div
          className="login-card"
          initial={{ opacity: 0, y: 26, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.6, ease: EASE, delay: 0.15 }}
        >
          <h1>🛡️ Sign in</h1>
          <div className="tag">Access the evidence console with your issued credentials.</div>
          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="username">Username</label>
              <input id="username" className="input" autoComplete="username" value={username}
                onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input id="password" type="password" className="input" autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && (
              <motion.div
                className="banner banner-error"
                role="alert"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, ease: EASE }}
              >
                <span className="icon">⚠️</span>
                <div><strong>Login failed</strong><div>{error.msg}</div>
                  {error.rid && <div className="rid">Request ID: {error.rid}</div>}</div>
              </motion.div>
            )}
            <motion.button
              type="submit"
              className="btn btn-primary btn-lg"
              style={{ width: '100%' }}
              disabled={busy}
              whileTap={busy ? undefined : { scale: 0.98 }}
            >
              {busy ? <><span className="spinner" /> Signing in…</> : 'Sign in to console'}
            </motion.button>
          </form>
          <div style={{ marginTop: 24 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', letterSpacing: 0.8, textTransform: 'uppercase' }}>
              Demo accounts — tap to fill
            </div>
            <motion.div
              className="demo-chips"
              variants={staggerParent}
              initial="hidden"
              animate="show"
            >
              {DEMO_USERS.map((u) => (
                <motion.button
                  key={u.username}
                  type="button"
                  className="chip"
                  onClick={() => quickFill(u.username)}
                  title={u.note}
                  variants={staggerChild}
                  whileTap={{ scale: 0.94 }}
                >
                  {u.username} <small>{ROLE_LABEL[u.role]}</small>
                </motion.button>
              ))}
            </motion.div>
            <div className="fictional-note">
              ⚠️ All accounts are <strong>fictional demo accounts</strong> seeded for this hackathon prototype.
              Password for every account: <code style={{ fontFamily: 'var(--mono)' }}>{DEMO_PASSWORD}</code>
            </div>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
