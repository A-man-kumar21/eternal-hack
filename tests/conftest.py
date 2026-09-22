"""Pytest fixtures: sqlite file DB + local storage, fresh seed per test."""
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="eabh-test-"))

os.environ["EABHILEKH_ENV"] = "test"
os.environ["EABHILEKH_MASTER_KEY"] = "ab" * 32  # 64 hex chars (test-only)
os.environ["EABHILEKH_JWT_SECRET"] = "test-jwt-secret"
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/test.db"
os.environ["MINIO_ENDPOINT"] = ""
os.environ["EABHILEKH_LOCAL_STORAGE"] = str(TMP / "storage")
os.environ["EABHILEKH_STAGING_DIR"] = str(TMP / "staging")
os.environ["CLAMAV_HOST"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import security  # noqa: E402
from app.db import get_session_factory, reset_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Case, CaseMember, Role, User  # noqa: E402

PASSWORD = "Demo@1234"

USERS = [
    ("inv.sharma", "R. Sharma", Role.INVESTIGATOR),
    ("leg.verma", "S. Verma", Role.LEGAL_REVIEWER),
    ("cust.iyer", "K. Iyer", Role.EVIDENCE_CUSTODIAN),
    ("aud.khan", "F. Khan", Role.SECURITY_AUDITOR),
    ("outsider.mehta", "J. Mehta", Role.INVESTIGATOR),
]


def _seed_users_and_case(db, case_number="CASE-TEST-1", members=("inv.sharma", "leg.verma",
                                                                "cust.iyer", "aud.khan")):
    users = {}
    for username, display, role in USERS:
        u = User(username=username, password_hash=security.hash_password(PASSWORD),
                 display_name=display, role=role)
        db.add(u)
        users[username] = u
    db.flush()
    inv = users["inv.sharma"]
    case = Case(case_number=case_number, title="Test case", description="t", created_by=inv.id)
    db.add(case)
    db.flush()
    for uname in members:
        db.add(CaseMember(case_id=case.id, user_id=users[uname].id,
                          role=users[uname].role, added_by=inv.id))
    db.commit()
    return users, case


@pytest.fixture()
def db():
    reset_engine()
    from app.db import get_engine

    eng = get_engine()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    session = get_session_factory()()
    _seed_users_and_case(session)
    yield session
    session.close()
    Base.metadata.drop_all(eng)


@pytest.fixture()
def client(db):
    return TestClient(app)


def login(client: TestClient, username: str, password: str = PASSWORD) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def authz(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
