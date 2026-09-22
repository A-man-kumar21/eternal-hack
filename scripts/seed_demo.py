"""Idempotent demo seed for e-Abhilekh.

Drops + recreates all tables, clears object storage, then seeds:
  - 5 fictional users (password for all: Demo@1234)
  - case CASE-2026-004 with the four role users as members (outsider excluded)
  - 4 sample evidence documents, each stamped "FICTIONAL DEMO DATA",
    pushed through the REAL ingest pipeline (stage_upload -> worker process_job)

Run:  python scripts/seed_demo.py
"""
from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _candidate in (ROOT / "apps" / "api", Path("/srv/api")):
    if (_candidate / "app").exists():
        sys.path.insert(0, str(_candidate))
        break

from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from app import security  # noqa: E402
from app.audit import write_audit  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_engine, get_session_factory, wipe_database  # noqa: E402
from app.models import (  # noqa: E402
    AuditOutcome,
    Case,
    CaseMember,
    DocType,
    User,
)
from app.services import cases as case_service  # noqa: E402
from app.services.ingest import process_job, stage_upload  # noqa: E402
from app.storage import get_storage  # noqa: E402

PASSWORD = "Demo@1234"  # fictional demo credential, documented in CONTRACT.md

USERS = [
    ("inv.sharma", "R. Sharma", "INVESTIGATOR"),
    ("leg.verma", "S. Verma", "LEGAL_REVIEWER"),
    ("cust.iyer", "K. Iyer", "EVIDENCE_CUSTODIAN"),
    ("aud.khan", "F. Khan", "SECURITY_AUDITOR"),
    ("outsider.mehta", "J. Mehta", "INVESTIGATOR"),
]


def make_pdf(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = A4[1] - 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(48, y, "FICTIONAL DEMO DATA — e-Abhilekh")
    y -= 30
    c.setFont("Helvetica", 11)
    for line in lines:
        for chunk in [line[i : i + 95] for i in range(0, len(line), 95)] or [""]:
            c.drawString(48, y, chunk)
            y -= 15
            if y < 60:
                c.showPage()
                y = A4[1] - 60
                c.setFont("Helvetica", 11)
    c.save()
    return buf.getvalue()


def make_png() -> bytes:
    img = Image.new("RGB", (640, 480), (30, 30, 40))
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 600, 440], outline=(200, 60, 60), width=4)
    d.text((70, 70), "FICTIONAL DEMO DATA", fill=(240, 240, 240))
    d.text((70, 110), "Evidence photo placeholder", fill=(200, 200, 200))
    d.text((70, 150), "CASE-2026-004", fill=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def seed() -> None:
    s = get_settings()
    engine = get_engine()
    wipe_database(engine)
    get_storage().clear_all()
    Path(s.EABHILEKH_STAGING_DIR).mkdir(parents=True, exist_ok=True)

    db = get_session_factory()()
    try:
        users: dict[str, User] = {}
        for username, display, role in USERS:
            u = User(username=username, password_hash=security.hash_password(PASSWORD),
                     display_name=display, role=role)
            db.add(u)
            users[username] = u
        db.flush()

        inv = users["inv.sharma"]
        case = case_service.create_case(
            db, inv, "CASE-2026-004", "Fictional Jewellery Theft — Demo Case",
            "Demo case for the e-Abhilekh prototype. All data is fictional.",
            request_id=f"seed-{uuid.uuid4().hex[:8]}",
        )
        for uname in ("leg.verma", "cust.iyer", "aud.khan"):
            db.add(CaseMember(case_id=case.id, user_id=users[uname].id,
                              role=users[uname].role, added_by=inv.id))
        db.flush()
        write_audit(
            db, action="CASE_MEMBER_ADD", outcome=AuditOutcome.ALLOWED, case_id=case.id,
            actor_id=inv.id, object_type="case", object_id=case.id,
            reason="seed: demo members added", request_id=f"seed-{uuid.uuid4().hex[:8]}",
        )
        db.commit()

        docs = [
            ("fir-report.pdf", "First Information Report", DocType.FIR,
             "FIR filed at the fictional demo police station.",
             make_pdf([
                 "FIRST INFORMATION REPORT (FICTIONAL)",
                 "Complainant: A. Fictional, ID 1234 5678 9012",
                 "Contact: 9876543210, email witness.fictional@example.com",
                 "Incident: theft of jewellery reported on 2026-01-15.",
                 "This document is entirely fictional and generated for demo purposes.",
             ])),
            ("evidence-photo.png", "Scene Photograph 1", DocType.EVIDENCE_PHOTO,
             "Placeholder evidence photograph (generated).",
             make_png()),
            ("charge-sheet-draft.pdf", "Charge Sheet (Draft)", DocType.CHARGE_SHEET,
             "Draft charge sheet for the fictional demo case.",
             make_pdf([
                 "CHARGE SHEET — DRAFT (FICTIONAL)",
                 "Accused: X. Fictional",
                 "Sections cited: fictional demo sections only.",
                 "Status: under preparation.",
             ])),
            ("witness-statement.txt", "Witness Statement", DocType.STATEMENT,
             "Fictional witness statement (plain text).",
             b"FICTIONAL DEMO DATA\nWitness statement (fictional):\n"
             b"I saw nothing. This is placeholder text for the demo.\n"),
        ]
        for filename, title, doc_type, desc, data in docs:
            doc, _job = stage_upload(
                db, user=inv, case_id=case.id, title=title, doc_type=doc_type,
                description=desc, file_bytes=data, original_filename=filename,
                request_id=f"seed-{uuid.uuid4().hex[:8]}",
            )
            db.commit()
            process_job(db, _job.id, get_storage(), request_id=f"seed-{uuid.uuid4().hex[:8]}")

        print("seed: done — 5 users, 1 case, 4 documents ingested")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
