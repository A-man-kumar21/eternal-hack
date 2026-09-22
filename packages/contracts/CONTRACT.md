# e-Abhilekh API Contract (v1) — frozen for parallel build

Base URL: `http://localhost:8000` · API prefix: `/api/v1` · OpenAPI at `/api/v1/openapi.json`.

## Global rules
- Auth: `Authorization: Bearer <access_token>` (JWT, HS256, 30-min expiry). Refresh via `/auth/refresh`. Logout revokes refresh token.
- Error envelope (all errors): `{"error": {"code": "SNAKE_CODE", "message": "human readable", "request_id": "<uuid>"}}`. Every response also carries `X-Request-ID` header.
- Every state-changing request accepts an optional `reason` field; the audit event stores it. Denied authorizations return **403** (not 404) AND write an audit event with `outcome: "DENIED"` AND surface in the alert center.
- Pagination: `?limit=50&offset=0` on list endpoints. Timestamps are ISO-8601 UTC.
- Roles: `INVESTIGATOR`, `LEGAL_REVIEWER`, `EVIDENCE_CUSTODIAN`, `SECURITY_AUDITOR`.

## Auth
- `POST /api/v1/auth/login` `{username, password}` → `{"access_token","refresh_token","token_type":"bearer","expires_in":1800,"user":{"id","username","display_name","role"}}`
- `POST /api/v1/auth/refresh` `{"refresh_token"}` → new token pair
- `POST /api/v1/auth/logout` → 204 (revokes refresh token)
- `GET /api/v1/users/me` → current user

## Users (for member assignment / demo switching)
- `GET /api/v1/users` → `[{"id","username","display_name","role"}]` (any authenticated user; demo convenience)

## Cases
- `POST /api/v1/cases` `{"case_number","title","description"}` → `201` Case. Creator auto-added as member with their own role.
- `GET /api/v1/cases` → cases the caller is a member of.
- `GET /api/v1/cases/{case_id}` → Case detail incl. `members[]` and `document_count`.
- `POST /api/v1/cases/{case_id}/members` `{"user_id","role"}` → `201`. Allowed for INVESTIGATOR and EVIDENCE_CUSTODIAN who are members.

Case: `{"id","case_number","title","description","status","created_by","created_at","members":[{"user_id","username","display_name","role"}]}`

## Documents (ingest pipeline)
- `POST /api/v1/cases/{case_id}/documents` multipart form: `file` (binary), `title`, `doc_type` ∈ {FIR, EVIDENCE_PHOTO, CHARGE_SHEET, COURT_FILING, STATEMENT, OTHER}, `description?`, `reason?` → `202 {"document_id","version_id","status":"INGESTING"}`. A background worker then runs: extension allowlist {pdf,jpg,jpeg,png,txt} → size ≤ 25 MB → MIME sniff must match extension → SHA-256 → AES-256-GCM envelope encrypt → store in object storage → status ACTIVE (or QUARANTINED with `quarantine_reason` on failure). Frontend polls `GET /documents/{id}` until `status` leaves INGESTING/QUARANTINED.
- `GET /api/v1/documents/{document_id}` → Document: `{"id","case_id","title","doc_type","description","status","current_version":{"id","version_number","sha256","size_bytes","mime_type","created_at","created_by"},"version_count","created_at"}` (+ `quarantine_reason` when relevant).
- `GET /api/v1/documents/{document_id}/versions` → all versions (original + derivatives), newest first.
- `GET /api/v1/documents/{document_id}/download?version_id?=&reason=` → decrypted file stream (Content-Disposition attachment). `reason` required for originals; logged.
- `POST /api/v1/documents/{document_id}/verify` → `{"document_id","version_id","stored_sha256","computed_sha256","match":bool,"verified_at"}`. If `match:false` → creates INCIDENT audit event + alert.
- `POST /api/v1/documents/{document_id}/freeze` `{"reason"}` → status FROZEN (custodian only).

## Custody
- `POST /api/v1/documents/{document_id}/custody` `{"action":"handoff|accept|release","to_user_id?","reason"}` → `201` CustodyEvent `{"id","document_id","action","from_user_id","to_user_id","reason","created_at"}`.
- `GET /api/v1/cases/{case_id}/timeline` → `{"events":[...]}` chronological, each `{"id","kind":"custody|audit|ingest|verify|redaction|export","actor","action","object_id","reason","created_at","detail"}`.

## Redaction (P1)
- `POST /api/v1/documents/{document_id}/redactions/analyze` → `{"version_id","marks":[{"mark_id","page","bbox":[x0,y0,x1,y1],"label":"AADHAAR|PHONE|EMAIL|NAME","confidence":0.0-1.0,"text_excerpt"}]}`. Rules-based detection on extracted text (regex for Aadhaar-like `\d{4}[\s-]?\d{4}[\s-]?\d{4}`, Indian phone, email); NER optional/stub.
- `POST /api/v1/documents/{document_id}/redactions` `{"approvals":[{"mark_id","approved":bool}],"reason"}` → `201 {"derivative_version_id","version_number","sha256"}`. Renders a new PDF with approved marks burned in as black overlays, text stripped under overlays, linked to parent version. Original untouched. (Legal reviewer or custodian only.)
- `GET /api/v1/documents/{document_id}/derivatives` → derivative versions with parent links.

## Export (P1)
- `POST /api/v1/cases/{case_id}/exports` `{"document_ids":[],"reason"}` → `202 {"bundle_id","status":"building"}` then `ready`; poll `GET /api/v1/exports/{bundle_id}` → `{"id","case_id","status","sha256","created_at","created_by","manifest":{...}}`.
- `GET /api/v1/exports/{bundle_id}/download` → ZIP containing files + `manifest.json` (case, documents, version hashes, custody summary, audit head hash) + `README.txt`.
- Manifest schema: `{"bundle_id","case_number","exported_at","exported_by","audit_chain_head","documents":[{"document_id","title","doc_type","version_number","sha256","custody":[...]}]}`.

## Audit & alerts
- `GET /api/v1/cases/{case_id}/audit?limit=&offset=` → audit events (auditor or member). Event: `{"id","case_id","actor_id","actor_name","action","object_type","object_id","outcome":"ALLOWED|DENIED|FAILED|INCIDENT","reason","request_id","created_at","event_hash","prev_hash"}`.
- `GET /api/v1/audit/verify-chain?case_id=` → `{"ok":bool,"events_checked":n,"broken_at_id":null|id}`. Recomputes every hash link.
- `GET /api/v1/alerts` → `{"alerts":[...]}` high-signal events (DENIED, INCIDENT, FAILED) newest first; auditor sees all cases, others see their cases.

## Demo/dev-only
- `POST /api/v1/dev/corrupt-blob/{version_id}` — flips one byte in stored ciphertext; **enabled only when `EABHILEKH_ENV=dev`**; writes audit event `DEMO_BLOB_CORRUPTED`. Powers the integrity-fail demo moment.
- `POST /api/v1/dev/reset` — **dev only**; wipes DB + storage and re-runs the seed script → exact demo state.

## Seeded demo identities (password for all: `Demo@1234` — fictional)
- `inv.sharma` INVESTIGATOR "R. Sharma" · `leg.verma` LEGAL_REVIEWER "S. Verma" · `cust.iyer` EVIDENCE_CUSTODIAN "K. Iyer" · `aud.khan` SECURITY_AUDITOR "F. Khan" · `outsider.mehta` INVESTIGATOR "J. Mehta" (NOT a member of the demo case — breach demo).

## Role permission matrix (service layer)
| action | INV | LEGAL | CUSTODIAN | AUDITOR |
|---|---|---|---|---|
| create case / add members | ✓ | – | add members ✓ | – |
| upload document | ✓ | – | ✓ | – |
| view/download (member) | ✓ | ✓ | ✓ | view only |
| custody handoff/accept | ✓ handoff | – | ✓ accept | – |
| freeze | – | – | ✓ | – |
| redaction review/approve | – | ✓ | ✓ | – |
| export bundle | – | ✓ | ✓ | – |
| audit read / verify chain | own case | own case | own case | **all cases** |
Any non-member access → 403 + DENIED audit event + alert.
