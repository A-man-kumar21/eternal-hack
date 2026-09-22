"""Audit anchors: append-only chain-head snapshots catch reforged history.

verify_chain() alone misses an admin who rewrites history AND recomputes
valid hashes. The anchor table records the head hash + chain length; the
anchored prefix is compared on every verify-chain call.
"""
from sqlalchemy import select

from app.audit import GENESIS, compute_event_hash
from app.models import AuditAnchor, AuditEvent

from .conftest import authz, login

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n"


def _case_id(client, token):
    return client.get("/api/v1/cases", headers=authz(token)).json()[0]["id"]


def _verify(client, token, case_id):
    r = client.get(f"/api/v1/audit/verify-chain?case_id={case_id}", headers=authz(token))
    assert r.status_code == 200, r.text
    return r.json()


def _upload(client, token, case_id, name="a.pdf"):
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(token),
        files={"file": (name, PDF_BYTES, "application/pdf")},
        data={"title": "t", "doc_type": "FIR"},
    )
    assert r.status_code == 202, r.text


def _anchor(client, token):
    r = client.post("/api/v1/audit/anchor", headers=authz(token))
    return r


def test_anchor_endpoint_is_auditor_only(client):
    inv_tok = login(client, "inv.sharma")["access_token"]
    aud_tok = login(client, "aud.khan")["access_token"]

    r = _anchor(client, inv_tok)
    assert r.status_code == 403

    r = _anchor(client, aud_tok)
    assert r.status_code == 201, r.text
    rows = r.json()
    assert len(rows) >= 1
    row = rows[0]
    assert row["anchored_hash"]
    assert row["events_anchored"] >= 0
    assert row["anchored_at"]


def test_anchor_is_append_only(client, db):
    aud_tok = login(client, "aud.khan")["access_token"]
    case_id = _case_id(client, aud_tok)

    assert _anchor(client, aud_tok).status_code == 201
    assert _anchor(client, aud_tok).status_code == 201

    rows = db.execute(
        select(AuditAnchor).where(AuditAnchor.case_id == case_id).order_by(AuditAnchor.id)
    ).scalars().all()
    assert len(rows) == 2  # never updated in place


def test_legit_appends_after_anchor_are_not_divergence(client):
    inv_tok = login(client, "inv.sharma")["access_token"]
    aud_tok = login(client, "aud.khan")["access_token"]
    case_id = _case_id(client, inv_tok)

    _upload(client, inv_tok, case_id)
    anchored = _anchor(client, aud_tok).json()[0]["anchored_hash"]

    # legitimate activity after the anchor must NOT look like tampering
    _upload(client, inv_tok, case_id, name="b.pdf")

    res = _verify(client, aud_tok, case_id)
    assert res["ok"] is True
    assert res["last_anchored_hash"] == anchored
    assert res["anchor_diverged"] is False


def _reforge_history(db, case_id):
    """Simulate a DB admin: rewrite the first event, recompute every hash."""
    events = db.execute(
        select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.id)
    ).scalars().all()
    assert len(events) >= 2
    events[0].reason = "rewritten by admin"
    prev = GENESIS
    for ev in events:
        ev.prev_hash = prev
        ev.event_hash = compute_event_hash(
            ev.prev_hash, ev.id, ev.created_at, ev.actor_id, ev.action,
            ev.case_id, ev.object_id, ev.outcome.value, ev.reason, ev.request_id,
        )
        prev = ev.event_hash
    db.commit()


def test_reforged_history_detected_via_anchor(client, db):
    """verify_chain() alone passes on reforged hashes; the anchor catches it."""
    inv_tok = login(client, "inv.sharma")["access_token"]
    aud_tok = login(client, "aud.khan")["access_token"]
    case_id = _case_id(client, inv_tok)

    _upload(client, inv_tok, case_id)
    _upload(client, inv_tok, case_id, name="b.pdf")
    assert _anchor(client, aud_tok).status_code == 201

    before = _verify(client, aud_tok, case_id)
    assert before["ok"] is True and before["anchor_diverged"] is False

    _reforge_history(db, case_id)

    res = _verify(client, aud_tok, case_id)
    # plain recompute is fooled: every link is internally consistent...
    assert res["ok"] is True
    assert res["broken_at_id"] is None
    # ...but the anchored prefix no longer matches: severe, distinct signal
    assert res["anchor_diverged"] is True
    assert res["last_anchored_hash"] == before["last_anchored_hash"]


def test_sloppy_tamper_is_a_normal_break_not_divergence(client, db):
    """Rewriting without reforging -> classic break; anchor prefix untouched."""
    from sqlalchemy import text

    inv_tok = login(client, "inv.sharma")["access_token"]
    aud_tok = login(client, "aud.khan")["access_token"]
    case_id = _case_id(client, inv_tok)

    _upload(client, inv_tok, case_id)
    _upload(client, inv_tok, case_id, name="b.pdf")
    assert _anchor(client, aud_tok).status_code == 201

    victim = db.execute(
        select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.id.desc())
    ).scalars().first()
    # tamper with the HEAD event only: stored hash unchanged, recompute fails,
    # but the anchored prefix (checked at the old head position) still matches
    db.execute(text("UPDATE audit_events SET reason = 'tampered' WHERE id = :i"),
               {"i": victim.id})
    db.commit()

    res = _verify(client, aud_tok, case_id)
    assert res["ok"] is False
    assert res["broken_at_id"] == victim.id
    assert res["anchor_diverged"] is False
