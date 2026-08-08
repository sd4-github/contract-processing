import json
import zipfile
from pathlib import PurePosixPath

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import core
from .audit import record_event
from .auth import Principal, require
from .database import get_session
from .models import Batch, ContractDocument, Finding
from .observability import configure as configure_observability
from .storage import document_storage
from .tasks import extract_document

configure_observability()

app = FastAPI(
    title="Contract Processing API",
    version="1.0.0-local",
    description="Bulk contract upload, mocked extraction, batch tracking, and reviewer decisions.",
)


class ReviewRequest(BaseModel):
    decision: str
    reviewer_name: str = Field(min_length=1, max_length=100)


def finding_out(item: Finding):
    fields = (
        "id", "variable_name", "extracted_value", "review_status",
        "reviewer_name", "reviewer_subject", "reviewed_at", "created_at",
    )
    return {key: getattr(item, key) for key in fields}


def document_out(item: ContractDocument):
    return {
        "id": item.id, "original_filename": item.original_filename,
        "size_bytes": item.size_bytes, "status": item.status,
        "error_message": item.error_message, "created_at": item.created_at,
        "processed_at": item.processed_at,
        "findings": [finding_out(finding) for finding in item.findings],
    }


def batch_out(item: Batch):
    return {
        "id": item.id, "variables": item.variables,
        "submitted_by_subject": item.submitted_by_subject, "status": item.status,
        "created_at": item.created_at, "completed_at": item.completed_at,
        "documents": [document_out(document) for document in item.documents],
    }


@app.get("/api/health/")
def health():
    return {"status": "ok"}


@app.post("/api/batches/", status_code=status.HTTP_202_ACCEPTED)
def create_batch(
    zip_file: UploadFile = File(...),
    variables: str = Form(...),
    principal: Principal = Depends(require("submitter", "administrator")),
    session: Session = Depends(get_session),
):
    try:
        fields = json.loads(variables)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "variables must be a JSON array of strings.") from exc
    valid_variables = (
        isinstance(fields, list)
        and fields
        and all(isinstance(value, str) and value.strip() for value in fields)
    )
    normalized_fields = [value.strip() for value in fields] if valid_variables else []
    valid_variables = valid_variables and len(set(normalized_fields)) == len(normalized_fields)
    if not valid_variables:
        raise HTTPException(422, "variables must be a non-empty, unique JSON array of strings.")
    # The persistence layer is synchronous SQLAlchemy, so keep this endpoint
    # synchronous as well. FastAPI runs it in its worker pool, avoiding an
    # async event-loop block while ZIP bytes and database rows are handled.
    payload = zip_file.file.read()
    try:
        archive = zipfile.ZipFile(__import__("io").BytesIO(payload))
        members = [entry for entry in archive.infolist() if not entry.is_dir()]
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, "Invalid ZIP archive.") from exc
    if not members or len(members) > core.MAX_DOCUMENTS:
        raise HTTPException(400, f"Archive must contain between 1 and {core.MAX_DOCUMENTS} documents.")
    for member in members:
        # Entries are read directly; never extract an archive to the filesystem.
        # This blocks traversal writes even when the ZIP is supplied by a user.
        path = PurePosixPath(member.filename)
        if path.is_absolute() or "\\" in member.filename or ".." in path.parts or path.suffix.lower() not in core.ALLOWED_EXTENSIONS or member.file_size > core.MAX_DOCUMENT_BYTES:
            raise HTTPException(400, "Archive contains an unsafe, unsupported, or oversized document.")
    batch = Batch(variables=normalized_fields, submitted_by_subject=principal.subject)
    session.add(batch)
    session.flush()
    document_ids = []
    for member in members:
        document = ContractDocument(batch_id=batch.id, original_filename=PurePosixPath(member.filename).name, storage_name=f"{batch.id}-{len(document_ids)}-{PurePosixPath(member.filename).name}", size_bytes=member.file_size)
        document_storage.save(document.storage_name, archive.read(member))
        session.add(document)
        session.flush()
        document_ids.append(document.id)
    # Commit database metadata before publishing tasks, so a worker cannot see
    # IDs from a transaction that later rolls back.
    session.commit()
    session.refresh(batch)
    for document_id in document_ids:
        extract_document.delay(document_id)
        record_event("document_queued", batch_id=batch.id, document_id=document_id)
    record_event("batch_created", batch_id=batch.id, document_count=len(document_ids), variables=batch.variables)
    return batch_out(batch)


@app.get("/api/batches/{batch_id}/")
def get_batch(batch_id: str, _: Principal = Depends(require("submitter", "reviewer", "administrator")), session: Session = Depends(get_session)):
    item = session.scalar(select(Batch).options(selectinload(Batch.documents).selectinload(ContractDocument.findings)).where(Batch.id == batch_id))
    if not item:
        raise HTTPException(404, "Not found.")
    return batch_out(item)


@app.get("/api/documents/{document_id}/")
def get_document(document_id: str, _: Principal = Depends(require("submitter", "reviewer", "administrator")), session: Session = Depends(get_session)):
    item = session.scalar(select(ContractDocument).options(selectinload(ContractDocument.findings)).where(ContractDocument.id == document_id))
    if not item:
        raise HTTPException(404, "Not found.")
    return document_out(item)


@app.patch("/api/findings/{finding_id}/review/")
def review_finding(finding_id: str, body: ReviewRequest, principal: Principal = Depends(require("reviewer", "administrator")), session: Session = Depends(get_session)):
    if body.decision not in {"accepted", "rejected"}:
        raise HTTPException(422, "decision must be accepted or rejected.")
    item = session.scalar(select(Finding).where(Finding.id == finding_id).with_for_update())
    if not item:
        raise HTTPException(404, "Not found.")
    item.review_status = body.decision
    item.reviewer_name = body.reviewer_name
    item.reviewer_subject = principal.subject
    from datetime import datetime, timezone
    item.reviewed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(item)
    record_event("finding_reviewed", finding_id=item.id, decision=item.review_status, reviewer_name=item.reviewer_name)
    return finding_out(item)
