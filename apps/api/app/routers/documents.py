from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from .. import schemas
from ..models import DocType, User
from ..services import custody as custody_service
from ..services import documents as doc_service
from ..services import export as export_service
from ..services import ingest as ingest_service
from ..services import redaction as redaction_service
from ..services.policy import require_case_access
from .deps import get_current_user, get_db, get_request_id

router = APIRouter()


@router.post("/cases/{case_id}/documents", response_model=schemas.UploadAcceptedOut,
             status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form(...),
    description: str = Form(""),
    reason: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    rid: str = Depends(get_request_id),
):
    require_case_access(db, user, case_id, "upload", rid, object_type="document")
    data = await file.read()
    doc, _job = ingest_service.stage_upload(
        db, user=user, case_id=case_id, title=title, doc_type=DocType(doc_type),
        description=description, file_bytes=data,
        original_filename=file.filename or "upload.bin", request_id=rid,
    )
    return {"document_id": doc.id, "version_id": None, "status": doc.status.value}


@router.get("/documents/{document_id}", response_model=schemas.DocumentOut)
def get_document(
    document_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    return schemas.DocumentOut(**doc_service.get_document(db, user, document_id, rid))


@router.get("/documents/{document_id}/versions", response_model=list[schemas.VersionOut])
def list_versions(
    document_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    return [schemas.VersionOut(**v) for v in doc_service.list_versions(db, user, document_id, rid)]


@router.get("/documents/{document_id}/download")
def download(
    document_id: int, version_id: int | None = Query(None), reason: str | None = Query(None),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
    rid: str = Depends(get_request_id),
):
    plaintext, filename, mime = doc_service.download(db, user, document_id, version_id, reason, rid)
    return Response(
        content=plaintext, media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/documents/{document_id}/verify", response_model=schemas.VerifyOut)
def verify(
    document_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    return schemas.VerifyOut(**doc_service.verify(db, user, document_id, rid))


@router.post("/documents/{document_id}/freeze", response_model=schemas.DocumentOut)
def freeze(
    document_id: int, body: schemas.FreezeIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    return schemas.DocumentOut(**doc_service.freeze(db, user, document_id, body.reason, rid))


# ---------- custody ----------
@router.post("/documents/{document_id}/custody", response_model=schemas.CustodyOut,
             status_code=status.HTTP_201_CREATED)
def custody(
    document_id: int, body: schemas.CustodyIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    ev = custody_service.record_custody(db, user, document_id, body.action, body.to_user_id, body.reason, rid)
    return schemas.CustodyOut(
        id=ev.id, document_id=ev.document_id, action=ev.action.value, from_user_id=ev.from_user_id,
        to_user_id=ev.to_user_id, reason=ev.reason, created_at=ev.created_at.isoformat(),
    )


# ---------- redaction ----------
@router.post("/documents/{document_id}/redactions/analyze", response_model=schemas.AnalyzeOut)
def analyze(
    document_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    res = redaction_service.analyze(db, user, document_id, rid)
    return schemas.AnalyzeOut(
        version_id=res["version_id"],
        marks=[schemas.RedactionMarkOut(**m) for m in res["marks"]],
        note=res.get("note"),
    )


@router.post("/documents/{document_id}/redactions", response_model=schemas.RedactOut,
             status_code=status.HTTP_201_CREATED)
def apply_redactions(
    document_id: int, body: schemas.RedactIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    deriv = redaction_service.apply_approvals(
        db, user, document_id,
        [{"mark_id": a.mark_id, "approved": a.approved} for a in body.approvals],
        rid,
    )
    return schemas.RedactOut(
        derivative_version_id=deriv.id, version_number=deriv.version_number, sha256=deriv.sha256,
    )


@router.get("/documents/{document_id}/derivatives", response_model=list[schemas.VersionOut])
def derivatives(
    document_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    rows = redaction_service.list_derivatives(db, user, document_id, rid)
    return [schemas.VersionOut(**doc_service.version_to_dict(v)) for v in rows]


# ---------- exports ----------
@router.post("/cases/{case_id}/exports", response_model=schemas.ExportAcceptedOut,
             status_code=status.HTTP_202_ACCEPTED)
def create_export(
    case_id: int, body: schemas.ExportIn, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    bundle = export_service.create_export(db, user, case_id, body.document_ids, body.reason, rid)
    return {"bundle_id": bundle.id, "status": bundle.status.value}


@router.get("/exports/{bundle_id}", response_model=schemas.ExportOut)
def get_export(
    bundle_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    b = export_service.get_export(db, user, bundle_id, rid)
    return schemas.ExportOut(
        id=b.id, case_id=b.case_id, status=b.status.value, sha256=b.sha256,
        created_at=b.created_at.isoformat(), created_by=b.created_by, manifest=b.manifest,
    )


@router.get("/exports/{bundle_id}/download")
def download_export(
    bundle_id: int, db: Session = Depends(get_db),
    user: User = Depends(get_current_user), rid: str = Depends(get_request_id),
):
    data, filename = export_service.download_export(db, user, bundle_id, rid)
    return Response(
        content=data, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
