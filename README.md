# e-Abhilekh — Secure Digital Document Management for Legal & Investigation Records

> *"Make integrity visible. Preserve every original. Prove every action."*

## What does our system do?

Law-enforcement and legal teams still move evidence across paper registers, shared
folders, and personal drives. Retrieval is slow, files can be quietly altered, and
trust depends on whoever kept the manual log. **e-Abhilekh replaces that with a
sealed, case-centric evidence vault** where every document is fingerprinted,
encrypted, access-controlled, and tracked from the moment it enters the system to
the moment it leaves for court.

Concretely, the system lets you:

- **Ingest securely** — upload FIRs, evidence photos, charge sheets, and court
  filings into a case. A background pipeline validates the file (type allowlist,
  size cap, MIME sniffing, optional ClamAV scan), computes its SHA-256 fingerprint,
  encrypts it with AES-256-GCM envelope encryption, and stores only ciphertext.
- **Prove integrity on demand** — anyone can re-verify a document: the system
  recomputes the hash and compares it against the stored fingerprint. A tampered
  byte produces a full-width **INTEGRITY FAILURE** banner and raises an incident.
- **Track custody** — every handoff (investigator → custodian → reviewer) is
  recorded with actor, action, timestamp, and reason, playable as a chronological
  timeline.
- **Redact safely** — legal reviewers get proposed PII marks (Aadhaar, phone,
  email), approve or reject each one, and the system generates a fresh,
  leak-checked redacted derivative. The original is never modified.
- **Enforce access** — four roles (Investigator, Legal Reviewer, Evidence
  Custodian, Security Auditor) with case-scoped permissions. Cross-case access
  attempts are denied, logged, and surfaced as alerts.
- **Export for court** — build an encrypted ZIP bundle with a `manifest.json`
  carrying file hashes, the custody summary, and the audit chain head hash — so
  the evidence speaks for itself instead of asking the court to trust a database.
- **Audit everything** — every action lands in an append-only, hash-chained
  (tamper-evident) audit log. The chain can be re-verified end to end at any time.

## Features

| Area | What you get |
|---|---|
| Authentication | Username/password (bcrypt), JWT access tokens (30 min), rotating refresh tokens (7 days), logout revocation |
| Authorization | Case-scoped role matrix enforced in the service layer; every denial writes a `DENIED` audit event + alert |
| Ingest pipeline | Extension allowlist → 25 MB cap → MIME sniff → SHA-256 → ClamAV (optional, degrades gracefully) → AES-256-GCM encrypt → object storage |
| Integrity | Stored vs recomputed SHA-256 verification; dev-only tamper simulator to demo failure |
| Encryption | Per-blob random 32-byte DEK, wrapped by master key via AES-256-GCM; ciphertext only on disk/storage |
| Custody | Handoffs with reason, freeze/unfreeze, chronological timeline playback |
| Versions | Every re-upload is a new immutable version linked to the original |
| Redaction | Human-reviewed marks, freshly rendered derivative PDF, automated leak check |
| Audit | Hash-chained per case (`GENESIS` → …), same-transaction writes, one-click chain verification |
| Alerts | Denials and integrity incidents surface in the Auditor Console (polls every 5 s) |
| Export | Synchronous encrypted ZIP: decrypted files + `manifest.json` + `README.txt` |

## Tech stack

- **Backend:** FastAPI, SQLAlchemy 2, Alembic, Pydantic — 28 routes
- **Frontend:** React 18, TypeScript, Vite, TanStack Query — dark "evidence console" theme
- **Database:** PostgreSQL 16 (SQLite for tests)
- **Storage:** MinIO (S3-compatible) with local-directory fallback
- **Worker:** DB-polling scan worker (no Celery/Redis — deliberate simplification)
- **Infra:** Docker Compose (postgres, minio, api, worker, web, optional ClamAV sidecar)

## Repo layout

| Path | Notes |
|---|---|
| `apps/api/` | FastAPI backend |
| `apps/web/` | React + TypeScript frontend |
| `workers/scan_worker.py` | DB-polling ingest worker |
| `scripts/seed_demo.py` | Idempotent demo seed (fictional data) |
| `scripts/gen_keys.py` | Generates the encryption keys for `.env` |
| `infra/compose.yaml` | postgres, minio, api, worker, web, optional clamav |
| `packages/contracts/CONTRACT.md` | API contract both sides build against |
| `tests/` | pytest suite (21 tests) |

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- [Git](https://git-scm.com/)
- [Python 3.11+](https://www.python.org/) (only for generating keys)

## Run it locally (Docker — recommended)

### Windows (PowerShell)

```powershell
# 1. Clone the repo
git clone https://github.com/A-man-kumar21/eternal-hack.git
cd eternal-hack

# 2. Create your env file
Copy-Item .env.example .env

# 3. Generate encryption keys and paste the two EABHILEKH_... lines into .env
python scripts/gen_keys.py
notepad .env

# 4. Build and start everything (postgres, minio, api, worker, web)
docker compose -f infra/compose.yaml up --build
```

Wait until you see `api-1 | INFO: Application startup complete` and the web
service is serving on port 3000. Press `d` to detach if you want the terminal back —
the containers keep running.

```powershell
# 5. Seed the demo data (dev only) — run in the same terminal after detaching,
#    or in a second PowerShell window
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/dev/reset
```

You should get back `{"reset": true, ...}`.

### Linux / macOS (bash)

```bash
# 1. Clone the repo
git clone https://github.com/A-man-kumar21/eternal-hack.git
cd eternal-hack

# 2. Create your env file
cp .env.example .env

# 3. Generate encryption keys and paste the two EABHILEKH_... lines into .env
python3 scripts/gen_keys.py
${EDITOR:-nano} .env

# 4. Build and start everything
docker compose -f infra/compose.yaml up --build
```

Then, in a second terminal:

```bash
# 5. Seed the demo data (dev only)
curl -X POST http://localhost:8000/api/v1/dev/reset
```

### Open the app

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API | http://localhost:8000 (OpenAPI docs at `/api/v1/docs`) |
| MinIO console | http://localhost:9001 |

### Log in (demo accounts — all data is fictional)

Password for **all** accounts: `Demo@1234`

| Username | Role |
|---|---|
| `inv.sharma` | Investigator |
| `leg.verma` | Legal Reviewer |
| `cust.iyer` | Evidence Custodian |
| `aud.khan` | Security Auditor |
| `outsider.mehta` | Not a member of any case — for the breach demo |

Start with `inv.sharma` and open the seeded case **CASE-2026-004**
("Fictional Jewellery Theft — Demo Case"). `outsider.mehta` is deliberately not a
member of the case: try opening it as the outsider to see a 403 denial get logged
and surfaced in the Auditor Console.

### Stopping

```powershell
docker compose -f infra/compose.yaml down        # stop containers
docker compose -f infra/compose.yaml down -v     # also wipe database + storage
```

## Run the backend without Docker (dev)

```bash
python -m venv .venv && .venv/bin/pip install -r apps/api/requirements.txt
cp .env.example .env && python scripts/gen_keys.py  # paste the two lines into .env
# point DATABASE_URL at postgres, or sqlite for a quick spin:
# DATABASE_URL=sqlite:////tmp/eabhilekh.db
cd apps/api && ../.venv/bin/alembic upgrade head && cd ../..
.venv/bin/python scripts/seed_demo.py
.venv/bin/uvicorn app.main:app --app-dir apps/api --port 8000 &
.venv/bin/python workers/scan_worker.py --interval 5 &
```

## Run the frontend without Docker (dev)

```bash
cd apps/web && npm install && npm run dev   # :5173, VITE_API_URL=http://localhost:8000
npm run build                                # -> dist/ (served by compose web service)
```

Pages: `/login` (demo-account quick-fill), `/cases`, `/cases/:id` (workspace:
upload, verify, custody, freeze, versions), `/cases/:id/timeline` (animated
custody playback), `/cases/:id/redact/:docId` (human-in-the-loop redaction
review), `/auditor` (alert feed polling every 5 s + chain verification),
`/cases/:id/export` (bundle builder + manifest preview).

## Tests

```bash
.venv/bin/python -m pytest -q   # sqlite + local storage, no external services
```

21 tests, covering auth, the role matrix, ingest, integrity, custody, redaction,
exports, and audit-chain verification.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker compose` fails pulling `minio/minio` | Already handled — compose pins `quay.io/minio/*` images since Docker Hub removed the official ones |
| Login says "Could not reach the API" | Make sure `api-1` shows "Application startup complete"; check `docker compose -f infra/compose.yaml logs api --tail 30` |
| Blank page after login | Fixed in current `main` — `git pull` and rebuild |
| `dev/reset` returns 500 on first run | Fixed in current `main` — `git pull` and rebuild |
| Port already in use | Stop whatever is on 3000/8000/5432/9000/9001, or edit the port mappings in `infra/compose.yaml` |
| Forgot the seed step | The app works without it, but the demo case and accounts only exist after `dev/reset` |

## Backend architecture

- **Auth**: bcrypt passwords; JWT HS256 access tokens (30 min); refresh tokens
  (7 days) stored hashed with rotation on refresh and revocation on logout.
- **Authorization** lives in `apps/api/app/services/policy.py` (service layer, not
  routers) and mirrors the contract's role matrix exactly. Every denial writes a
  `DENIED` audit event and returns 403 with the error envelope.
- **Audit hash chain**: `event_hash = sha256(canonical JSON {prev_hash, id,
  timestamp_utc, actor_id, action, case_id, object_id, outcome, reason, request_id})`,
  chained per case (`GENESIS` for the first). Business change + audit event are
  committed in the **same DB transaction**. `GET /audit/verify-chain?case_id=`
  recomputes the whole chain.
- **Envelope encryption**: random 32-byte DEK per blob, AES-256-GCM file
  encryption, DEK wrapped with the master key (`EABHILEKH_MASTER_KEY`, 32 bytes
  hex) via AES-256-GCM. Only ciphertext touches object storage / disk.
- **Storage**: boto3 → MinIO when `MINIO_ENDPOINT` is set, else a local-directory
  fallback with the same put/get interface. Uploaded filenames are never used as
  paths — object keys are server-generated UUIDs.
- **Ingest pipeline** (`workers/scan_worker.py` → `services/ingest.py`): extension
  allowlist → 25 MB cap → MIME sniff must match extension → SHA-256 → ClamAV
  INSTREAM if `CLAMAV_HOST` set (graceful `{"av":"skipped"}` otherwise) → encrypt →
  store. Failures quarantine the document with a reason. Idempotent per job.
- **Redaction** (documented simplification): text-based PDFs carry no reliable
  glyph coordinates, so marks have `bbox: null` and the UI lists them textually.
  The derivative is a freshly rendered PDF (cover page + extracted text with
  approved spans replaced by black bars); the original is untouched. A leak check
  asserts no approved span survives in the derivative bytes/text. Image OCR uses
  pytesseract only if installed, else marks are empty.
- **Export**: synchronous build; ZIP (decrypted ACTIVE/FROZEN files +
  `manifest.json` + `README.txt`) is envelope-encrypted at rest; download
  decrypts and streams. Manifest includes the audit chain head hash.
- **Dev-only** (`EABHILEKH_ENV=dev`, else 404): `POST /dev/corrupt-blob/{version_id}`
  flips one ciphertext byte (audit `DEMO_BLOB_CORRUPTED`); `POST /dev/reset`
  wipes DB + storage and reseeds.

## Simplifications vs the contract

1. `redaction_marks` gained a `matched_text` column (exact regex hit, powers the
   leak check); `export_bundles` gained `wrapped_dek/dek_nonce/gcm_nonce/gcm_tag`
   columns (bundles are encrypted blobs too).
2. Redaction bboxes are `null` for text PDFs (documented above); coordinates are
   not fabricated.
3. Export builds synchronously — the POST returns `{"status":"ready"}` immediately
   instead of `building`→poll.
4. Added `GET /cases/{case_id}/documents` (list) — not in the contract, harmless.
5. `documents.current_version_id` has no DB-level FK (self-referential cycle);
   enforced by the app.
6. `bcrypt` pinned to `<4.1` — passlib 1.7.x is broken with bcrypt ≥ 4.1.

## Six-minute demo script

Seed first (`POST http://localhost:8000/api/v1/dev/reset`), then log in —
password `Demo@1234` for all fictional accounts.

| Time | Beat | Who | What the audience sees |
|---|---|---|---|
| 0:00 | The gap | inv.sharma | "Evidence moves across paper registers and shared folders. Retrieval is slow; trust depends on manual logs." |
| 0:35 | Secure ingest | inv.sharma | Upload the FIR PDF → status pulses INGESTING → worker validates, scans, hashes, encrypts → ACTIVE. Show the SHA-256. |
| 1:35 | Integrity proof | inv.sharma | Verify → green, hashes match. Then the prepared tampered copy: hit "Demo: simulate tamper", verify again → full-width red **INTEGRITY FAILURE**, incident logged. |
| 2:30 | Custody proof | inv.sharma → cust.iyer | Timeline playback: hand evidence to the custodian with a reason; each event shows actor, action, time, reason. |
| 3:25 | Privacy proof | leg.verma | Redaction review: Aadhaar/phone/email marks proposed → approve → derivative PDF generated, linked to the untouched original. |
| 4:30 | Access proof | outsider.mehta → aud.khan | Log in as the outsider (not a case member) → 403 + request ID. Switch to the auditor → the denial is already in the alert feed. |
| 5:15 | Court-ready close | cust.iyer | Export selected versions → download ZIP → open `manifest.json`: files, hashes, custody summary, audit chain head. "We don't ask the court to trust our database." |

Backup plan: rehearse on a clean `dev/reset`; keep a screen recording as fallback
only. If asked about admin tampering → show chain verification failing on a
forged row (the `verify-chain` endpoint). If asked about keys → master key from
env/KMS in production, per-object DEKs here.

## Deployment notes (honest limitations)

- **Prototype, not production.** Single-node docker compose; no HA, no backups
  configured (add Postgres WAL + MinIO versioning before any real use).
- **Audit chain is tamper-evident, not immutable.** An admin with DB access could
  rewrite rows — the chain makes it *detectable*, not impossible. Production
  should anchor periodic chain heads in independently controlled storage.
- **Master key** comes from `EABHILEKH_MASTER_KEY` env. Production needs a KMS/HSM;
  never commit `.env`.
- **ClamAV is optional** and degrades to `{"av":"skipped"}` when unset — the demo
  relies on allowlist + size + MIME sniffing. Do not claim AV protection without
  the sidecar.
- **Redaction is regex-assisted + human-reviewed.** Coordinates are not
  fabricated for text PDFs; the derivative is a freshly rendered, leak-checked
  PDF, not a pixel overlay on the original.
- **All data is fictional.** Never load real personal, police, or legal records
  into this prototype. Demo password `Demo@1234` is intentionally weak and must
  never be reused.
