import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import core
from .audit import record_event
from .models import Batch, ContractDocument, Finding
from .storage import document_storage


def extract_values(content: bytes, variables: list[str]) -> dict[str, str]:
    seed = int(hashlib.sha256(content).hexdigest()[:12], 16)
    values = {}
    for index, variable in enumerate(variables):
        number, normalized = seed + index, variable.lower()
        if "date" in normalized:
            values[variable] = str(date(2024, 1, 1) + timedelta(days=number % 730))
        elif any(term in normalized for term in ("rent", "deposit", "charge", "amount", "price")):
            values[variable] = f"INR {Decimal(5000 + number % 195001):,.2f}"
        elif "period" in normalized or "notice" in normalized:
            values[variable] = f"{30 + number % 91} days"
        elif "law" in normalized:
            values[variable] = ("India", "England and Wales", "Singapore")[number % 3]
        else:
            values[variable] = f"mock-{variable}-{number % 100000}"
    return values


def refresh_batch_status(session: Session, batch: Batch) -> None:
    # Derive this aggregate while holding one source of truth: document states,
    # rather than trusting independently incremented worker counters.
    statuses = [document.status for document in batch.documents]
    if not statuses or "processing" in statuses:
        batch.status = "processing"
    elif "pending" in statuses:
        batch.status = "pending"
    elif all(state == "completed" for state in statuses):
        batch.status = "completed"
    elif all(state == "failed" for state in statuses):
        batch.status = "failed"
    else:
        batch.status = "partial_failed"
    if batch.status in {"completed", "failed", "partial_failed"}:
        batch.completed_at = datetime.now(timezone.utc)


def process_document(session: Session, document_id: str) -> None:
    document = session.scalar(select(ContractDocument).options(selectinload(ContractDocument.batch).selectinload(Batch.documents)).where(ContractDocument.id == document_id))
    # At-least-once brokers can redeliver a completed task. The terminal-state
    # guard and unique finding key make that delivery harmless.
    if not document or document.status == "completed":
        return
    document.status, document.error_message = "processing", ""
    session.commit()
    record_event("document_processing_started", batch_id=document.batch_id, document_id=document.id)
    try:
        values = extract_values(document_storage.read(document.storage_name), document.batch.variables)
        for name, value in values.items():
            finding = session.scalar(select(Finding).where(Finding.document_id == document.id, Finding.variable_name == name))
            if finding:
                finding.extracted_value = value
            else:
                session.add(Finding(document_id=document.id, variable_name=name, extracted_value=value))
        document.status, document.processed_at = "completed", datetime.now(timezone.utc)
        record_event("document_processing_completed", batch_id=document.batch_id, document_id=document.id)
    except Exception as exc:
        document.status, document.error_message = "failed", str(exc)[:2000]
        record_event("document_processing_failed", document_id=document_id, error=str(exc))
        raise
    finally:
        refresh_batch_status(session, document.batch)
        session.commit()
