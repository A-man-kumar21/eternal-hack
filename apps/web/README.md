# e-Abhilekh — Web Frontend

Evidence-console frontend for the e-Abhilekh hackathon prototype
("Secure Digital Document Management System for Legal & Investigation Records").

React 18 + TypeScript + Vite + TanStack Query + react-router-dom, hand-written CSS
(dark evidence-console theme). Built strictly against
`packages/contracts/CONTRACT.md` (frozen v1).

## Dev

```bash
npm install
npm run dev        # serves on :5173, expects the API at VITE_API_URL
```

## Build

```bash
npm run build      # tsc + vite build → dist/ (served by the Docker image)
```

## Config

| Env var        | Default                 | Purpose                          |
|----------------|-------------------------|----------------------------------|
| `VITE_API_URL` | `http://localhost:8000` | API base URL (no `/api/v1` suffix) |

See `.env.example`.

## Routes

| Route                        | Page                                                        |
|------------------------------|-------------------------------------------------------------|
| `/login`                     | Sign-in + fictional demo-account quick-fill chips           |
| `/cases`                     | Case dashboard + new-case dialog                            |
| `/cases/:id`                 | Case workspace: ingest dropzone, doc list, detail drawer    |
| `/cases/:id/timeline`        | Custody playback (animated chronological feed)              |
| `/cases/:id/redact/:docId`   | Redaction review: approve marks → generate derivative       |
| `/cases/:id/export`          | Export bundle builder + manifest preview + ZIP download     |
| `/auditor`                   | Alert feed (5s poll), audit table, verify-chain             |

## Notes

- Tokens live in `localStorage`; 401 → single refresh attempt → redirect to `/login`.
- Every error surface shows the human message **and** the `X-Request-ID` from the
  contract's error envelope.
- Privileged/destructive actions (freeze, custody, original download, redaction
  render, export) always prompt for a reason first.
- The doc list has **no contracted list endpoint** — see `src/api/hooks.ts` for the
  graceful fallback (probe `GET /cases/{id}/documents`, else derive IDs from
  timeline ingest events).
