"""Upload validation: bad extension, MIME mismatch -> quarantine, oversize 413."""
from app.db import get_session_factory
from app.services.ingest import process_pending

from .conftest import authz, login

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n"


def _case_id(client, token):
    return client.get("/api/v1/cases", headers=authz(token)).json()[0]["id"]


def _upload(client, token, case_id, filename, data, mime="application/octet-stream"):
    return client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(token),
        files={"file": (filename, data, mime)},
        data={"title": "t", "doc_type": "OTHER"},
    )


def _run_worker():
    s = get_session_factory()()
    try:
        return process_pending(s)
    finally:
        s.close()


def test_bad_extension_rejected(client):
    tok = login(client, "inv.sharma")["access_token"]
    case_id = _case_id(client, tok)
    r = _upload(client, tok, case_id, "evil.exe", b"MZ...")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_oversize_rejected_413(client):
    tok = login(client, "inv.sharma")["access_token"]
    case_id = _case_id(client, tok)
    big = b"a" * (25 * 1024 * 1024 + 1)
    r = _upload(client, tok, case_id, "big.pdf", big)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_mime_mismatch_quarantined(client):
    tok = login(client, "inv.sharma")["access_token"]
    case_id = _case_id(client, tok)
    # .pdf extension but plain-text content -> worker quarantines
    r = _upload(client, tok, case_id, "fake.pdf", b"just some plain text, not a pdf")
    assert r.status_code == 202
    doc_id = r.json()["document_id"]
    assert _run_worker() == 1

    r = client.get(f"/api/v1/documents/{doc_id}", headers=authz(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "QUARANTINED"
    assert "MIME mismatch" in (body.get("quarantine_reason") or "")


def test_happy_path_becomes_active(client):
    tok = login(client, "inv.sharma")["access_token"]
    case_id = _case_id(client, tok)
    r = _upload(client, tok, case_id, "real.pdf", PDF_BYTES, mime="application/pdf")
    assert r.status_code == 202
    doc_id = r.json()["document_id"]
    assert _run_worker() == 1

    r = client.get(f"/api/v1/documents/{doc_id}", headers=authz(tok))
    body = r.json()
    assert body["status"] == "ACTIVE"
    assert body["current_version"]["mime_type"] == "application/pdf"
    assert len(body["current_version"]["sha256"]) == 64

    # scan job is idempotent: reprocessing does nothing harmful
    assert _run_worker() == 0
    r = client.get(f"/api/v1/documents/{doc_id}", headers=authz(tok))
    assert r.json()["status"] == "ACTIVE"
