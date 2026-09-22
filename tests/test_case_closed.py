"""Closed-case enforcement: mutating actions on a CLOSED case -> 403 + DENIED audit.

Reads (view/download/audit_read), custody_release and export stay available.
"""
from sqlalchemy import select

from app.models import AuditEvent, AuditOutcome, Case, User

from .conftest import authz, login

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n"


def _case_id(client, token):
    return client.get("/api/v1/cases", headers=authz(token)).json()[0]["id"]


def _user_id(db, username):
    return db.execute(select(User.id).where(User.username == username)).scalar_one()


def _close_case(db, case_id):
    case = db.get(Case, case_id)
    case.status = "CLOSED"
    db.commit()


def _upload_doc(client, token, case_id):
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(token),
        files={"file": ("fir.pdf", PDF_BYTES, "application/pdf")},
        data={"title": "FIR copy", "doc_type": "FIR"},
    )
    assert r.status_code == 202, r.text
    return r.json()["document_id"]


def _latest_denied(db, case_id):
    # End any open read transaction on the fixture session so we see the
    # request-scoped sessions' commits (SQLite snapshot isolation).
    db.rollback()
    return db.execute(
        select(AuditEvent)
        .where(AuditEvent.case_id == case_id, AuditEvent.outcome == AuditOutcome.DENIED)
        .order_by(AuditEvent.id.desc())
        .limit(1)
    ).scalar_one()


def _assert_blocked(client, db, case_id, response, expected_audit_action):
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "FORBIDDEN"
    ev = _latest_denied(db, case_id)
    assert ev.action == expected_audit_action, f"expected {expected_audit_action}, got {ev.action}"
    assert "CLOSED" in (ev.reason or "")


def test_closed_case_blocks_all_mutating_actions(client, db):
    inv_tok = login(client, "inv.sharma")["access_token"]
    leg_tok = login(client, "leg.verma")["access_token"]
    cust_tok = login(client, "cust.iyer")["access_token"]
    case_id = _case_id(client, inv_tok)

    # positive control: everything works while the case is OPEN
    doc_id = _upload_doc(client, inv_tok, case_id)

    _close_case(db, case_id)

    # reads still work on a closed case
    r = client.get(f"/api/v1/cases/{case_id}", headers=authz(inv_tok))
    assert r.status_code == 200, r.text

    cust_id = _user_id(db, "cust.iyer")
    outsider_id = _user_id(db, "outsider.mehta")

    # upload
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(inv_tok),
        files={"file": ("fir2.pdf", PDF_BYTES, "application/pdf")},
        data={"title": "late FIR", "doc_type": "FIR"},
    )
    _assert_blocked(client, db, case_id, r, "DOCUMENT_UPLOAD")

    # freeze
    r = client.post(
        f"/api/v1/documents/{doc_id}/freeze",
        headers=authz(cust_tok),
        json={"reason": "trial ended"},
    )
    _assert_blocked(client, db, case_id, r, "DOCUMENT_FREEZE")

    # custody handoff
    r = client.post(
        f"/api/v1/documents/{doc_id}/custody",
        headers=authz(inv_tok),
        json={"action": "handoff", "to_user_id": cust_id, "reason": "transfer"},
    )
    _assert_blocked(client, db, case_id, r, "CUSTODY_HANDOFF")

    # custody accept
    r = client.post(
        f"/api/v1/documents/{doc_id}/custody",
        headers=authz(cust_tok),
        json={"action": "accept", "reason": "taking custody"},
    )
    _assert_blocked(client, db, case_id, r, "CUSTODY_ACCEPT")

    # redact
    r = client.post(
        f"/api/v1/documents/{doc_id}/redactions",
        headers=authz(leg_tok),
        json={"approvals": [], "reason": "pii"},
    )
    _assert_blocked(client, db, case_id, r, "REDACTION_APPLY")

    # add_member
    r = client.post(
        f"/api/v1/cases/{case_id}/members",
        headers=authz(inv_tok),
        json={"user_id": outsider_id, "role": "INVESTIGATOR"},
    )
    _assert_blocked(client, db, case_id, r, "CASE_MEMBER_ADD")
