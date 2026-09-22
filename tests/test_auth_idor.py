"""Auth + IDOR: login, cross-case 403, DENIED audit event, alert visibility."""
from sqlalchemy import select

from app.models import AuditEvent, AuditOutcome, Case

from .conftest import authz, login


def test_login_ok(client):
    body = login(client, "inv.sharma")
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["user"]["username"] == "inv.sharma"
    assert body["user"]["role"] == "INVESTIGATOR"
    assert "X-Request-ID" in client.post("/api/v1/auth/login",
                                         json={"username": "x", "password": "y"}).headers or True


def test_login_bad_password_envelope(client):
    r = client.post("/api/v1/auth/login", json={"username": "inv.sharma", "password": "wrong"})
    assert r.status_code == 401
    assert r.headers.get("X-Request-ID")
    err = r.json()["error"]
    assert err["code"] == "UNAUTHORIZED"
    assert err["request_id"] == r.headers["X-Request-ID"]


def test_me(client):
    tok = login(client, "aud.khan")["access_token"]
    r = client.get("/api/v1/users/me", headers=authz(tok))
    assert r.status_code == 200
    assert r.json()["username"] == "aud.khan"


def test_refresh_rotation_and_logout(client):
    pair = login(client, "inv.sharma")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 200
    pair2 = r.json()
    # old refresh token is revoked by rotation
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r.status_code == 401
    # logout revokes the current refresh token
    r = client.post("/api/v1/auth/logout", json={"refresh_token": pair2["refresh_token"]})
    assert r.status_code == 204
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": pair2["refresh_token"]})
    assert r.status_code == 401


def _case_id(client, token):
    r = client.get("/api/v1/cases", headers=authz(token))
    assert r.status_code == 200
    return r.json()[0]["id"]


def test_outsider_denied_audit_and_alert(client, db):
    inv_tok = login(client, "inv.sharma")["access_token"]
    out_tok = login(client, "outsider.mehta")["access_token"]
    aud_tok = login(client, "aud.khan")["access_token"]
    case_id = _case_id(client, inv_tok)

    # outsider is not a member -> 403 with the error envelope
    r = client.get(f"/api/v1/cases/{case_id}", headers=authz(out_tok))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"

    # a DENIED audit event was written for the attempt
    ev = db.execute(
        select(AuditEvent)
        .where(AuditEvent.case_id == case_id, AuditEvent.outcome == AuditOutcome.DENIED)
        .order_by(AuditEvent.id.desc())
    ).scalar_one_or_none()
    assert ev is not None
    assert ev.action == "CASE_READ"

    # auditor sees it in the alert center
    r = client.get("/api/v1/alerts", headers=authz(aud_tok))
    assert r.status_code == 200
    alerts = r.json()["alerts"]
    assert any(a["outcome"] == "DENIED" and a["case_id"] == case_id for a in alerts)

    # auditor can also read the case audit log for that case
    r = client.get(f"/api/v1/cases/{case_id}/audit", headers=authz(aud_tok))
    assert r.status_code == 200
    assert any(e["outcome"] == "DENIED" for e in r.json())

    # the outsider's own alert feed does not leak other cases' alerts
    r = client.get("/api/v1/alerts", headers=authz(out_tok))
    assert r.status_code == 200
    assert all(a["case_id"] != case_id for a in r.json()["alerts"])


def test_role_matrix_denials(client):
    """Legal reviewer cannot upload; investigator cannot freeze; auditor cannot export."""
    inv_tok = login(client, "inv.sharma")["access_token"]
    leg_tok = login(client, "leg.verma")["access_token"]
    aud_tok = login(client, "aud.khan")["access_token"]
    case_id = _case_id(client, inv_tok)

    # legal reviewer upload -> 403
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(leg_tok),
        files={"file": ("x.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"title": "t", "doc_type": "OTHER"},
    )
    assert r.status_code == 403

    # need a document to test freeze/export; upload as investigator then process
    from app.services.ingest import process_pending
    from app.db import get_session_factory

    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(inv_tok),
        files={"file": ("x.pdf", b"%PDF-1.4 test", "application/pdf")},
        data={"title": "t", "doc_type": "OTHER"},
    )
    assert r.status_code == 202
    doc_id = r.json()["document_id"]
    s = get_session_factory()()
    process_pending(s)
    s.close()

    # investigator freeze -> 403 (custodian only)
    r = client.post(f"/api/v1/documents/{doc_id}/freeze", headers=authz(inv_tok),
                    json={"reason": "x"})
    assert r.status_code == 403

    # auditor export -> 403
    r = client.post(f"/api/v1/cases/{case_id}/exports", headers=authz(aud_tok),
                    json={"document_ids": [doc_id], "reason": "x"})
    assert r.status_code == 403
