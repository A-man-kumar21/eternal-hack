import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

const PIPELINE = [
  { icon: '📥', name: 'Ingest', desc: 'Type allowlist · 25 MB cap · MIME sniff' },
  { icon: '🔍', name: 'Validate', desc: 'SHA-256 fingerprint · ClamAV scan' },
  { icon: '🔐', name: 'Encrypt', desc: 'AES-256-GCM envelope, per-blob DEK' },
  { icon: '🗄️', name: 'Seal', desc: 'Ciphertext only · immutable versions' },
  { icon: '⛓️', name: 'Attest', desc: 'Hash-chained audit event written' },
];

const PILLARS = [
  {
    icon: '🔑', title: 'Sealed access control',
    desc: 'Four roles, case-scoped permissions enforced in the service layer. Every cross-case attempt is denied, logged, and raised as an alert.',
  },
  {
    icon: '🗂️', title: 'Immutable versioning',
    desc: 'Every re-upload is a new version linked to the original. Originals are never modified — redactions produce fresh derivatives.',
  },
  {
    icon: '⛓️', title: 'Tamper-evident audit',
    desc: 'Every action lands in an append-only, hash-chained log. Re-verify the whole chain in one click; anchored checkpoints catch history rewrites.',
  },
  {
    icon: '🔐', title: 'Encrypted storage',
    desc: 'Per-document data keys wrapped by a master key. Only ciphertext touches disk — a stolen drive yields nothing.',
  },
];

const MOMENTS = [
  {
    icon: '✅', title: 'Prove integrity',
    desc: 'Recompute SHA-256 against the stored fingerprint. A green banner certifies the bytes are untouched.',
  },
  {
    icon: '🚨', title: 'Catch tampering',
    desc: 'Flip one ciphertext byte and verify again — full-width INTEGRITY FAILURE banner, incident raised to the Auditor Console.',
  },
  {
    icon: '🚫', title: 'Stop a breach',
    desc: 'Sign in as an outsider and open a foreign case → 403 DENIED, written to the audit log and surfaced as an alert.',
  },
];

export default function Landing() {
  const { user } = useAuth();
  return (
    <div className="landing">
      <header className="landing-top">
        <Link to="/" className="brand">
          <span className="shield">🛡️</span>
          <span>e-Abhilekh<small>Evidence Console</small></span>
        </Link>
        <div className="row">
          <span className="pill pill-amber">PS-24 · Hackathon prototype</span>
          <Link to={user ? '/dashboard' : '/login'} className="btn btn-primary btn-sm">
            {user ? 'Open console →' : 'Launch live demo →'}
          </Link>
        </div>
      </header>

      <section className="landing-hero">
        <div className="eyebrow">SECURE DIGITAL DOCUMENT MANAGEMENT · LEGAL &amp; INVESTIGATION RECORDS</div>
        <h1>Evidence you can <em>prove</em>.</h1>
        <p className="lede">
          Investigation records still move through paper registers, shared folders and personal
          drives. Files get quietly altered, retrieval takes days, and trust depends on whoever
          kept the manual log. <strong>e-Abhilekh</strong> seals every FIR, evidence photo, charge
          sheet and court filing in a case-centric vault — fingerprinted, encrypted,
          access-controlled, and tracked from intake to the courtroom.
        </p>
        <div className="row wrap" style={{ marginTop: 26 }}>
          <Link to={user ? '/dashboard' : '/login'} className="btn btn-primary btn-lg">
            {user ? 'Open console →' : 'Launch live demo →'}
          </Link>
          <a href="#pipeline" className="btn btn-ghost btn-lg">How it works ↓</a>
        </div>
        <div className="hero-term">
          <span className="prompt">$</span> verify-chain --case CASE-2026-004
          <span className="ok"> → ok: true · hash links intact</span>
        </div>
      </section>

      <section id="pipeline" className="landing-section">
        <h2>Every file travels through a sealed pipeline</h2>
        <p className="section-sub">From the moment a document enters the system, five gates stand between it and silent tampering.</p>
        <div className="pipeline">
          {PIPELINE.map((s, i) => (
            <div key={s.name} className="pipe-step">
              <div className="pipe-icon">{s.icon}</div>
              <div className="pipe-name">{i + 1}. {s.name}</div>
              <div className="pipe-desc">{s.desc}</div>
              {i < PIPELINE.length - 1 && <div className="pipe-arrow">→</div>}
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <h2>Four guarantees, engineered in</h2>
        <p className="section-sub">Not policies on paper — enforcement in code, on every request.</p>
        <div className="pillar-grid">
          {PILLARS.map((p) => (
            <div key={p.title} className="card pillar-card">
              <div className="pillar-icon">{p.icon}</div>
              <h3>{p.title}</h3>
              <p>{p.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-section">
        <h2>Three moments that win the room</h2>
        <p className="section-sub">Open the live demo and run these beats — each maps to one judging criterion.</p>
        <div className="pillar-grid">
          {MOMENTS.map((m) => (
            <div key={m.title} className="card pillar-card">
              <div className="pillar-icon">{m.icon}</div>
              <h3>{m.title}</h3>
              <p>{m.desc}</p>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 26, textAlign: 'center' }}>
          <Link to={user ? '/dashboard' : '/login'} className="btn btn-primary btn-lg">
            {user ? 'Open console →' : 'Try it live — demo accounts on the login page →'}
          </Link>
        </div>
      </section>

      <footer className="landing-foot">
        <div>🛡️ e-Abhilekh · hackathon prototype</div>
        <div style={{ color: 'var(--faint)', fontSize: 12.5, marginTop: 6 }}>
          All accounts, cases and documents in the demo are fictional. FastAPI · React · PostgreSQL · AES-256-GCM · SHA-256.
        </div>
      </footer>
    </div>
  );
}
