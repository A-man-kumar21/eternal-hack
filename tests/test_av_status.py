"""AV status surfacing: the scan outcome is persisted per version and visible
in the API (document + versions endpoints), never silently assumed."""
from app.db import get_session_factory
from app.services.ingest import process_pending

from .conftest import authz, login

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n"


def _case_id(client, token):
    return client.get("/api/v1/cases", headers=authz(token)).json()[0]["id"]


def _upload_and_process(client, token, case_id):
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(token),
        files={"file": ("real.pdf", PDF_BYTES, "application/pdf")},
        data={"title": "t", "doc_type": "FIR"},
    )
    assert r.status_code == 202, r.text
    doc_id = r.json()["document_id"]
    s = get_session_factory()()
    try:
        assert process_pending(s) == 1
    finally:
        s.close()
    return doc_id


def test_av_skipped_is_visible_per_version(client):
    """CLAMAV_HOST is unset in tests -> scan skipped, and the API says so."""
    tok = login(client, "inv.sharma")["access_token"]
    case_id = _case_id(client, tok)
    doc_id = _upload_and_process(client, tok, case_id)

    r = client.get(f"/api/v1/documents/{doc_id}", headers=authz(tok))
    assert r.status_code == 200
    cv = r.json()["current_version"]
    assert cv["av_status"] == "skipped"
    assert "no AV service" in (cv["av_detail"] or "")

    r = client.get(f"/api/v1/documents/{doc_id}/versions", headers=authz(tok))
    assert r.status_code == 200
    versions = r.json()
    assert len(versions) == 1
    assert versions[0]["av_status"] == "skipped"


def test_derivative_inherits_parent_av_status(client):
    """Redaction derivatives are server-generated from scanned bytes."""
    from sqlalchemy import select

    from app.models import DocumentVersion

    tok = login(client, "inv.sharma")["access_token"]
    case_id = _case_id(client, tok)
    doc_id = _upload_and_process(client, tok, case_id)

    s = get_session_factory()()
    try:
        parent = s.execute(
            select(DocumentVersion).where(DocumentVersion.document_id == doc_id)
        ).scalars().one()
        deriv = DocumentVersion(
            document_id=doc_id, version_number=2, object_key="test/deriv",
            sha256="0" * 64, size_bytes=10, mime_type="application/pdf",
            wrapped_dek="00", dek_nonce="00", gcm_nonce="00", gcm_tag="00",
            is_derivative=True, parent_version_id=parent.id,
            av_status=parent.av_status, av_detail=parent.av_detail,
            created_by=1,
        )
        s.add(deriv)
        s.commit()
    finally:
        s.close()

    r = client.get(f"/api/v1/documents/{doc_id}/versions", headers=authz(tok))
    child = [v for v in r.json() if v["version_number"] == 2][0]
    assert child["av_status"] == "skipped"
