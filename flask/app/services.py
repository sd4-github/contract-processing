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
    seed, result = int(hashlib.sha256(content).hexdigest()[:12], 16), {}
    for index, variable in enumerate(variables):
        number, name = seed + index, variable.lower()
        if "date" in name:
            result[variable] = str(date(2024, 1, 1) + timedelta(days=number % 730))
        elif any(term in name for term in ("rent", "deposit", "charge", "amount", "price")):
            result[variable] = f"INR {Decimal(5000 + number % 195001):,.2f}"
        elif "period" in name or "notice" in name:
            result[variable] = f"{30 + number % 91} days"
        elif "law" in name:
            result[variable] = ("India", "England and Wales", "Singapore")[number % 3]
        else:
            result[variable] = f"mock-{variable}-{number % 100000}"
    return result


def refresh_batch_status(session: Session, batch: Batch) -> None:
    # The batch is an aggregate of durable document states, which survives
    # crashes and duplicate queue messages more reliably than counters.
    states = [item.status for item in batch.documents]
    if not states or "processing" in states:
        batch.status = "processing"
    elif "pending" in states:
        batch.status = "pending"
    elif all(state == "completed" for state in states):
        batch.status = "completed"
    elif all(state == "failed" for state in states):
        batch.status = "failed"
    else:
        batch.status = "partial_failed"
    if batch.status in {"completed", "failed", "partial_failed"}:
        batch.completed_at = datetime.now(timezone.utc)


def process_document(session: Session, document_id: str) -> None:
    statement = (
        select(ContractDocument)
        .options(selectinload(ContractDocument.batch).selectinload(Batch.documents))
        .where(ContractDocument.id == document_id)
    )
    document = session.scalar(statement)
    # Celery provides at-least-once delivery. A terminal completed record is the
    # idempotency key; the database uniqueness constraint protects findings.
    if not document or document.status == "completed":
        return
    document.status = "processing"
    document.error_message = ""
    session.commit()
    record_event("document_processing_started", batch_id=document.batch_id, document_id=document.id)
    try:
        content = document_storage.read(document.storage_name)
        values = extract_values(content, document.batch.variables)
        for name, value in values.items():
            finding = session.scalar(
                select(Finding).where(
                    Finding.document_id == document.id,
                    Finding.variable_name == name,
                )
            )
            if finding:
                finding.extracted_value = value
            else:
                session.add(
                    Finding(
                        document_id=document.id,
                        variable_name=name,
                        extracted_value=value,
                    )
                )
        document.status = "completed"
        document.processed_at = datetime.now(timezone.utc)
        record_event("document_processing_completed", batch_id=document.batch_id, document_id=document.id)
    except Exception as exc:
        document.status = "failed"
        document.error_message = str(exc)[:2000]
        record_event("document_processing_failed", document_id=document_id, error=str(exc))
        raise
    finally:
        refresh_batch_status(session, document.batch)
        session.commit()
