import { useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import type { Role } from '../api/types';
import { ROLE_LABEL } from '../api/types';
import { useAuth } from '../auth/AuthContext';

/** Fictional seeded demo accounts — per CONTRACT.md. Password for all: Demo@1234 */
const DEMO_USERS: Array<{ username: string; display_name: string; role: Role; note: string }> = [
  { username: 'inv.sharma', display_name: 'R. Sharma', role: 'INVESTIGATOR', note: 'uploads, custody handoff' },
  { username: 'leg.verma', display_name: 'S. Verma', role: 'LEGAL_REVIEWER', note: 'redaction review, export' },
  { username: 'cust.iyer', display_name: 'K. Iyer', role: 'EVIDENCE_CUSTODIAN', note: 'freeze, accept custody' },
  { username: 'aud.khan', display_name: 'F. Khan', role: 'SECURITY_AUDITOR', note: 'audit + alerts, all cases' },
  { username: 'outsider.mehta', display_name: 'J. Mehta', role: 'INVESTIGATOR', note: 'not a case member — breach demo' },
];

const DEMO_PASSWORD = 'Demo@1234';

export default function Login() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<{ msg: string; rid: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && user) return <Navigate to="/cases" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      navigate('/cases', { replace: true });
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
    <div className="page-narrow">
      <div className="login-wrap">
        <div className="card login-card">
          <h1>🛡️ e-Abhilekh</h1>
          <div className="tag">Secure digital document management for legal &amp; investigation records</div>
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
              <div className="banner banner-error" role="alert">
                <span className="icon">⚠️</span>
                <div><strong>Login failed</strong><div>{error.msg}</div>
                  {error.rid && <div className="rid">Request ID: {error.rid}</div>}</div>
              </div>
            )}
            <button type="submit" className="btn btn-primary btn-lg" style={{ width: '100%' }} disabled={busy}>
              {busy ? <><span className="spinner" /> Signing in…</> : 'Sign in'}
            </button>
          </form>
          <div style={{ marginTop: 22 }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--muted)', letterSpacing: 0.5, textTransform: 'uppercase' }}>
              Demo accounts — tap to fill
            </div>
            <div className="demo-chips">
              {DEMO_USERS.map((u) => (
                <button key={u.username} type="button" className="chip" onClick={() => quickFill(u.username)} title={u.note}>
                  {u.username} <small>{ROLE_LABEL[u.role]}</small>
                </button>
              ))}
            </div>
            <div className="fictional-note">
              ⚠️ All accounts are <strong>fictional demo accounts</strong> seeded for this hackathon prototype.
              Password for every account: <code style={{ fontFamily: 'var(--mono)' }}>{DEMO_PASSWORD}</code>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
