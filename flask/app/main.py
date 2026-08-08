import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

from flask import Flask, g, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import core
from .audit import record_event
from .auth import require
from .database import SessionLocal
from .models import Batch, ContractDocument, Finding
from .observability import configure as configure_observability
from .storage import document_storage
from .tasks import extract_document

configure_observability()


def finding_out(item):
    fields = (
        "id", "variable_name", "extracted_value", "review_status",
        "reviewer_name", "reviewer_subject", "reviewed_at", "created_at",
    )
    return {key: getattr(item, key) for key in fields}


def document_out(item):
    return {
        "id": item.id, "original_filename": item.original_filename,
        "size_bytes": item.size_bytes, "status": item.status,
        "error_message": item.error_message, "created_at": item.created_at,
        "processed_at": item.processed_at,
        "findings": [finding_out(finding) for finding in item.findings],
    }


def batch_out(item):
    return {
        "id": item.id, "variables": item.variables,
        "submitted_by_subject": item.submitted_by_subject, "status": item.status,
        "created_at": item.created_at, "completed_at": item.completed_at,
        "documents": [document_out(document) for document in item.documents],
    }


def create_app():
    app = Flask(__name__)

    @app.get("/api/health/")
    def health():
        return {"status": "ok"}

    @app.post("/api/batches/")
    @require("submitter", "administrator")
    def create_batch():
        upload = request.files.get("zip_file")
        raw_variables = request.form.get("variables")
        if not upload or raw_variables is None:
            return {"detail": "zip_file and variables are required."}, 400
        try:
            variables = json.loads(raw_variables)
        except json.JSONDecodeError:
            return {"detail": "variables must be a JSON array of strings."}, 422
        valid_variables = (
            isinstance(variables, list)
            and variables
            and all(isinstance(value, str) and value.strip() for value in variables)
        )
        normalized_variables = [value.strip() for value in variables] if valid_variables else []
        valid_variables = valid_variables and len(normalized_variables) == len(set(normalized_variables))
        if not valid_variables:
            return {"detail": "variables must be a non-empty, unique JSON array of strings."}, 422
        try:
            archive = zipfile.ZipFile(io.BytesIO(upload.read()))
            members = [member for member in archive.infolist() if not member.is_dir()]
        except zipfile.BadZipFile:
            return {"detail": "Invalid ZIP archive."}, 400
        if not members or len(members) > core.MAX_DOCUMENTS:
            return {"detail": f"Archive must contain between 1 and {core.MAX_DOCUMENTS} documents."}, 400
        for member in members:
            path = PurePosixPath(member.filename)
            # Validate central-directory metadata before persisting any records;
            # ZIP members are never extracted as paths on the host filesystem.
            if path.is_absolute() or "\\" in member.filename or ".." in path.parts or path.suffix.lower() not in core.ALLOWED_EXTENSIONS or member.file_size > core.MAX_DOCUMENT_BYTES:
                return {"detail": "Archive contains an unsafe, unsupported, or oversized document."}, 400
        with SessionLocal() as session:
            batch = Batch(
                variables=normalized_variables,
                submitted_by_subject=g.subject,
            )
            session.add(batch)
            session.flush()
            document_ids = []
            for member in members:
                filename = PurePosixPath(member.filename).name
                document = ContractDocument(
                    batch_id=batch.id, original_filename=filename,
                    storage_name=f"{batch.id}-{len(document_ids)}-{filename}",
                    size_bytes=member.file_size,
                )
                document_storage.save(document.storage_name, archive.read(member))
                session.add(document)
                session.flush()
                document_ids.append(document.id)
            # Publish only after commit so workers cannot observe rolled-back IDs.
            session.commit()
            session.refresh(batch)
            result = batch_out(batch)
        for document_id in document_ids:
            extract_document.delay(document_id)
            record_event("document_queued", batch_id=result["id"], document_id=document_id)
        record_event(
            "batch_created", batch_id=result["id"],
            document_count=len(document_ids), variables=result["variables"],
        )
        return result, 202

    @app.get("/api/batches/<batch_id>/")
    @require("submitter", "reviewer", "administrator")
    def get_batch(batch_id):
        with SessionLocal() as session:
            statement = (
                select(Batch)
                .options(selectinload(Batch.documents).selectinload(ContractDocument.findings))
                .where(Batch.id == batch_id)
            )
            item = session.scalar(statement)
            if not item:
                return {"detail": "Not found."}, 404
            return batch_out(item)

    @app.get("/api/documents/<document_id>/")
    @require("submitter", "reviewer", "administrator")
    def get_document(document_id):
        with SessionLocal() as session:
            statement = (
                select(ContractDocument)
                .options(selectinload(ContractDocument.findings))
                .where(ContractDocument.id == document_id)
            )
            item = session.scalar(statement)
            if not item:
                return {"detail": "Not found."}, 404
            return document_out(item)

    @app.patch("/api/findings/<finding_id>/review/")
    @require("reviewer", "administrator")
    def review_finding(finding_id):
        body = request.get_json(silent=True) or {}
        valid_request = (
            body.get("decision") in {"accepted", "rejected"}
            and isinstance(body.get("reviewer_name"), str)
            and 1 <= len(body.get("reviewer_name")) <= 100
        )
        if not valid_request:
            return {"detail": "decision and reviewer_name are required."}, 422
        with SessionLocal() as session:
            item = session.scalar(select(Finding).where(Finding.id == finding_id).with_for_update())
            if not item:
                return {"detail": "Not found."}, 404
            item.review_status = body["decision"]
            item.reviewer_name = body["reviewer_name"]
            item.reviewer_subject = g.subject
            item.reviewed_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(item)
            record_event(
                "finding_reviewed", finding_id=item.id,
                decision=item.review_status, reviewer_name=item.reviewer_name,
            )
            return finding_out(item)
    return app


app = create_app()
