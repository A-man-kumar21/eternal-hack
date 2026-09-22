"""Redaction: approved PII spans must be absent from the derivative."""
import io

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.db import get_session_factory
from app.services.ingest import process_pending

from .conftest import authz, login

AADHAAR = "1234 5678 9012"
PHONE = "9876543210"
EMAIL = "witness.fictional@example.com"


def _pii_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 11)
    y = A4[1] - 60
    for line in [
        "FICTIONAL DEMO DATA",
        f"Complainant ID {AADHAAR}",
        f"Contact {PHONE} / {EMAIL}",
        "Nothing else to see here.",
    ]:
        c.drawString(48, y, line)
        y -= 16
    c.save()
    return buf.getvalue()


def _upload_and_ingest(client, token, case_id):
    r = client.post(
        f"/api/v1/cases/{case_id}/documents",
        headers=authz(token),
        files={"file": ("fir.pdf", _pii_pdf(), "application/pdf")},
        data={"title": "FIR", "doc_type": "FIR"},
    )
    assert r.status_code == 202
    doc_id = r.json()["document_id"]
    s = get_session_factory()()
    process_pending(s)
    s.close()
    return doc_id


def test_redaction_no_leak(client):
    inv_tok = login(client, "inv.sharma")["access_token"]
    leg_tok = login(client, "leg.verma")["access_token"]
    case_id = client.get("/api/v1/cases", headers=authz(inv_tok)).json()[0]["id"]
    doc_id = _upload_and_ingest(client, inv_tok, case_id)

    r = client.post(f"/api/v1/documents/{doc_id}/redactions/analyze", headers=authz(leg_tok))
    assert r.status_code == 200
    body = r.json()
    labels = {m["label"] for m in body["marks"]}
    assert {"AADHAAR", "PHONE", "EMAIL"} <= labels
    assert all(m["bbox"] is None for m in body["marks"])  # documented simplification

    approvals = [{"mark_id": m["mark_id"], "approved": True} for m in body["marks"]]
    r = client.post(f"/api/v1/documents/{doc_id}/redactions",
                    headers=authz(leg_tok), json={"approvals": approvals, "reason": "demo"})
    assert r.status_code == 201
    deriv_id = r.json()["derivative_version_id"]

    # download the DERIVATIVE (no reason required) and check for leaks
    r = client.get(f"/api/v1/documents/{doc_id}/download?version_id={deriv_id}",
                   headers=authz(leg_tok))
    assert r.status_code == 200
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(r.content)).pages)
    assert AADHAAR not in text
    assert PHONE not in text
    assert EMAIL not in text
    assert AADHAAR.encode() not in r.content

    # derivatives listing shows the parent link
    r = client.get(f"/api/v1/documents/{doc_id}/derivatives", headers=authz(leg_tok))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["is_derivative"] is True
    assert r.json()[0]["parent_version_id"] == body["version_id"]


def test_redaction_reviewer_roles(client):
    """Investigator (not legal/custodian) cannot approve redactions."""
    inv_tok = login(client, "inv.sharma")["access_token"]
    case_id = client.get("/api/v1/cases", headers=authz(inv_tok)).json()[0]["id"]
    doc_id = _upload_and_ingest(client, inv_tok, case_id)

    r = client.post(f"/api/v1/documents/{doc_id}/redactions/analyze", headers=authz(inv_tok))
    assert r.status_code == 403
