"""Encryption: ciphertext != plaintext, roundtrip works, wrong key fails."""
import pytest

from app import crypto


def test_roundtrip():
    enc = crypto.encrypt_blob(b"top secret evidence bytes")
    assert enc["ciphertext"] != b"top secret evidence bytes".hex()
    assert len(enc["sha256"]) == 64
    pt = crypto.decrypt_blob(
        enc["ciphertext"], enc["wrapped_dek"], enc["dek_nonce"], enc["gcm_nonce"], enc["gcm_tag"]
    )
    assert pt == b"top secret evidence bytes"


def test_wrong_master_key_fails():
    enc = crypto.encrypt_blob(b"data")
    with pytest.raises(Exception):
        crypto.decrypt_blob(
            enc["ciphertext"], enc["wrapped_dek"], enc["dek_nonce"],
            enc["gcm_nonce"], enc["gcm_tag"], master_key=b"\x00" * 32,
        )


def test_tampered_ciphertext_fails():
    enc = crypto.encrypt_blob(b"data")
    ct = bytearray(bytes.fromhex(enc["ciphertext"]))
    ct[0] ^= 0xFF
    with pytest.raises(Exception):
        crypto.decrypt_blob(
            ct.hex(), enc["wrapped_dek"], enc["dek_nonce"], enc["gcm_nonce"], enc["gcm_tag"]
        )


def test_random_dek_per_blob():
    a = crypto.encrypt_blob(b"same")
    b = crypto.encrypt_blob(b"same")
    assert a["ciphertext"] != b["ciphertext"]
    assert a["wrapped_dek"] != b["wrapped_dek"]
    assert a["sha256"] == b["sha256"]  # same plaintext -> same hash


def test_dev_corrupt_blob_demo_flow(client):
    """End-to-end integrity demo: corrupt blob -> verify match=false + INCIDENT alert."""
    import os

    from app.config import get_settings

    os.environ["EABHILEKH_ENV"] = "dev"
    get_settings.cache_clear()
    try:
        from app.db import get_session_factory
        from app.services.ingest import process_pending

        from .conftest import authz, login

        inv_tok = login(client, "inv.sharma")["access_token"]
        aud_tok = login(client, "aud.khan")["access_token"]
        case_id = client.get("/api/v1/cases", headers=authz(inv_tok)).json()[0]["id"]

        r = client.post(
            f"/api/v1/cases/{case_id}/documents",
            headers=authz(inv_tok),
            files={"file": ("a.pdf", b"%PDF-1.4 demo", "application/pdf")},
            data={"title": "t", "doc_type": "FIR"},
        )
        doc_id = r.json()["document_id"]
        s = get_session_factory()()
        process_pending(s)
        s.close()
        version_id = client.get(f"/api/v1/documents/{doc_id}",
                                headers=authz(inv_tok)).json()["current_version"]["id"]

        r = client.post(f"/api/v1/dev/corrupt-blob/{version_id}", headers=authz(inv_tok))
        assert r.status_code == 200

        r = client.post(f"/api/v1/documents/{doc_id}/verify", headers=authz(inv_tok))
        body = r.json()
        assert body["match"] is False

        r = client.get("/api/v1/alerts", headers=authz(aud_tok))
        assert any(a["outcome"] == "INCIDENT" for a in r.json()["alerts"])
    finally:
        os.environ["EABHILEKH_ENV"] = "test"
        get_settings.cache_clear()


def test_dev_endpoints_disabled_outside_dev(client):
    import os

    from app.config import get_settings

    os.environ["EABHILEKH_ENV"] = "prod"
    get_settings.cache_clear()
    try:
        from .conftest import authz, login

        tok = login(client, "inv.sharma")["access_token"]
        r = client.post("/api/v1/dev/corrupt-blob/1", headers=authz(tok))
        assert r.status_code == 404
        r = client.post("/api/v1/dev/reset", headers=authz(tok))
        assert r.status_code == 404
    finally:
        os.environ["EABHILEKH_ENV"] = "test"
        get_settings.cache_clear()
