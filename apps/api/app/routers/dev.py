"""Dev-only demo endpoints. HARD-DISABLED unless EABHILEKH_ENV=dev (404 otherwise)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..audit import write_audit
from ..config import get_settings
from ..errors import NotFound
from ..models import AuditOutcome, DocumentVersion, User
from ..storage import get_storage
from .deps import get_current_user, get_db, get_request_id

router = APIRouter()


def _require_dev() -> None:
    if get_settings().EABHILEKH_ENV != "dev":
        # Indistinguishable from a missing route.
        raise NotFound("Not found")


@router.post("/dev/corrupt-blob/{version_id}")
def corrupt_blob(
    version_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    _require_dev()
    version = db.get(DocumentVersion, version_id)
    if version is None:
        raise NotFound("Version not found")
    storage = get_storage()
    raw = bytearray(storage.get_bytes(version.object_key))
    if not raw:
        raise NotFound("Blob is empty")
    raw[0] ^= 0xFF  # flip one byte of the stored ciphertext
    storage.put_bytes(version.object_key, bytes(raw))

    from ..models import Document
    doc = db.get(Document, version.document_id)
    write_audit(
        db, action="DEMO_BLOB_CORRUPTED", outcome=AuditOutcome.ALLOWED, case_id=doc.case_id,
        actor_id=user.id, object_type="document_version", object_id=version.id,
        reason="demo: flipped one ciphertext byte to showcase integrity verification",
        request_id=rid,
    )
    db.commit()
    return {"version_id": version_id, "corrupted": True, "request_id": rid}


@router.post("/dev/reset")
def reset(rid: str = Depends(get_request_id)):
    _require_dev()
    import runpy
    from pathlib import Path

    here = Path(__file__).resolve()
    candidates = [
        here.parents[4] / "scripts" / "seed_demo.py",  # repo checkout layout
        Path("/srv/scripts/seed_demo.py"),            # docker image layout
    ]
    seed_path = next((p for p in candidates if p.exists()), None)
    if seed_path is None:
        raise NotFound("seed script not found")

    # Wipe only AFTER we know the seed script exists — a failed reset must
    # never leave the database empty.
    from ..db import get_engine, wipe_database

    engine = get_engine()
    wipe_database(engine)
    get_storage().clear_all()
    runpy.run_path(str(seed_path), run_name="__main__")
    return {"reset": True, "request_id": rid}
