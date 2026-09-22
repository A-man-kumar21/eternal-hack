# e-Abhilekh — Demo script (presenter notes)

**Setup (do this 10 minutes before):** start the stack, hit **↺ Reset demo data** on the
dashboard (or `POST /api/v1/dev/reset`), confirm the dashboard shows CHAIN VERIFIED.
Password for every fictional account: `Demo@1234`. All data is fictional.

**Golden rule:** never type a password on stage — use the demo chips on the login page.

---

## Beat 0 — The story (0:00, landing page, no login)

> "Investigation records still move through paper registers, shared folders and
> personal drives. Files get quietly altered, retrieval takes days, and trust
> depends on whoever kept the manual log."

Scroll once through the pipeline strip. End on: **"Evidence you can prove."**
Click **Launch live demo**.

## Beat 1 — Command deck (0:40, log in as `inv.sharma`)

Land on the dashboard. Point at three things, in order:

1. The green **CHAIN VERIFIED** banner — "before I show you anything, the system
   proves its own audit log is intact."
2. Stat cards — cases, sealed documents, open alerts.
3. Latest alerts — "denials and incidents surface here within seconds."

## Beat 2 — Secure ingest (1:10, `inv.sharma`, case workspace)

Upload any PDF → watch **INGESTING pulse → ACTIVE**. Open the document:

- SHA-256 fingerprint, full hash visible.
- The **AV badge** — "every version carries its scan verdict; nothing is silently assumed clean."

## Beat 3 — Integrity proof (2:00, `inv.sharma`)

1. **Verify** → green banner, hashes match.
2. **"Demo: simulate tamper"** → flips one byte of stored ciphertext.
3. **Verify again** → full-width red **INTEGRITY FAILURE**.
4. Flip to the Auditor Console → the incident is already in the alert feed.

> "Integrity isn't a claim here. It's falsifiable — live, in front of you."

## Beat 4 — Chain proof (2:50, `aud.khan`, Auditor Console)

Select the case → **🔗 Verify chain**. The chain visualization lights up block by
block, genesis → latest, every link green, each block showing
`hash ← prev`.

> "This is what tamper-evidence looks like when you stop hiding it in a database table."

If asked about admin tampering: "An admin could rewrite rows — the chain makes it
*detectable*, not impossible. Anchored checkpoints catch a full history rewrite."

## Beat 5 — Custody proof (3:40, `inv.sharma` → `cust.iyer`)

Timeline tab: the seeded handoff is already there (investigator → custodian with a
reason). Optionally do a live handoff. Every event: actor, action, timestamp, reason.

## Beat 6 — Privacy proof (4:25, `leg.verma`, Redaction tab)

The FIR already has proposed marks (Aadhaar / phone / email). Approve → generate
the derivative → show v2 linked to the untouched v1 original.

> "The original is never modified. The court gets the redacted copy; the evidence
> locker keeps the original."

## Beat 7 — Access proof (5:10, `outsider.mehta` → `aud.khan`)

Log out → log in as `outsider.mehta` (chip notes: *not a case member*) → open the
case → **403 + request ID**. Switch to `aud.khan` → the denial is in the alert feed.

> "Every 'no' is evidence too."

## Beat 8 — Court-ready close (5:45, `cust.iyer`, Export tab)

Build the bundle → download the ZIP → open `manifest.json`: file hashes, custody
summary, audit chain head hash.

> **"We don't ask the court to trust our database."**

---

## If things go wrong

- **Backend not in dev mode:** the ↺ reset button explains itself; fall back to the
  already-seeded data.
- **Demo gods:** keep a screen recording of beats 2–4 as backup; narrate over it.
- **"Is ClamAV running?"** → "The pipeline degrades honestly — the badge says
  *AV skipped*, never *clean*, when no scanner is attached."

## Screenshot shot list (`docs/screenshots/`)

1. `01-landing.png` — hero, full viewport
2. `02-dashboard.png` — verified banner + stats
3. `03-workspace.png` — document detail with AV badge
4. `04-tamper.png` — INTEGRITY FAILURE banner
5. `05-chain-viz.png` — chain viz mid-verification
6. `06-export.png` — manifest.json open beside the ZIP
