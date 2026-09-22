"""Audit hash chain: verify ok, then tamper a row -> verify fails."""
from sqlalchemy import select, text

from app.db import get_session_factory
from app.models import AuditEvent
from app.services.ingest import process_pending

from .conftest import authz, login

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n"


def _case_id(client, token):
    return client.get("/api/v1/cases", headers=authz(token)).json()[0]["id"]


def _verify(client, token, case_id):
    r = client.get(f"/api/v1/audit/verify-chain?case_id={case_id}", headers=authz(token))
    assert r.status_code == 200
    return r.json()


def test_chain_verifies_ok(client):
    tok = login(client, "inv.sharma")["access_token"]
    case_id = _case_id(client, tok)

    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(tok),
        files={"file": ("a.pdf", PDF_BYTES, "application/pdf")},
        data={"title": "t", "doc_type": "FIR"},
    )
    assert r.status_code == 202
    s = get_session_factory()()
    process_pending(s)
    s.close()

    res = _verify(client, tok, case_id)
    assert res["ok"] is True
    assert res["events_checked"] > 0
    assert res["broken_at_id"] is None


def test_chain_detects_tamper(client, db):
    from app.db import get_session_factory
    from app.services.ingest import process_pending

    tok = login(client, "inv.sharma")["access_token"]
    case_id = _case_id(client, tok)

    # generate some case-scoped audit events first
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(tok),
        files={"file": ("a.pdf", PDF_BYTES, "application/pdf")},
        data={"title": "t", "doc_type": "FIR"},
    )
    assert r.status_code == 202
    s = get_session_factory()()
    process_pending(s)
    s.close()
    assert _verify(client, tok, case_id)["ok"] is True

    victim = db.execute(
        select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.id)
    ).scalars().first()
    assert victim is not None

    # tamper directly in the DB, bypassing the app (simulates insider/DB tampering)
    db.execute(text("UPDATE audit_events SET reason = 'tampered' WHERE id = :i"), {"i": victim.id})
    db.commit()

    res = _verify(client, tok, case_id)
    assert res["ok"] is False
    assert res["broken_at_id"] == victim.id


def test_verify_chain_denied_for_outsider(client):
    inv_tok = login(client, "inv.sharma")["access_token"]
    out_tok = login(client, "outsider.mehta")["access_token"]
    case_id = _case_id(client, inv_tok)
    r = client.get(f"/api/v1/audit/verify-chain?case_id={case_id}", headers=authz(out_tok))
    assert r.status_code == 403
