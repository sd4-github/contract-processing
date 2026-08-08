from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Batch, ContractDocument, Finding
from app.services import process_document
from app.storage import document_storage
from app.tasks import extract_document


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def make_batch(document_count=2):
    with SessionLocal() as session:
        batch = Batch(variables=["effective_date"])
        session.add(batch)
        session.flush()
        documents = []
        for number in range(document_count):
            document = ContractDocument(
                batch_id=batch.id,
                original_filename=f"contract-{number}.txt",
                storage_name=f"test-{batch.id}-{number}.txt",
                size_bytes=4,
            )
            session.add(document)
            session.flush()
            document_storage.save(document.storage_name, b"text")
            documents.append(document.id)
        session.commit()
        return batch.id, documents


def test_duplicate_delivery_is_idempotent(monkeypatch):
    _, document_ids = make_batch(1)
    monkeypatch.setattr("app.services.record_event", lambda *args, **kwargs: None)
    with SessionLocal() as session:
        process_document(session, document_ids[0])
        process_document(session, document_ids[0])
        findings = session.scalars(select(Finding).where(Finding.document_id == document_ids[0])).all()
    assert len(findings) == 1


def test_partial_failure_aggregates_batch_status(monkeypatch):
    batch_id, document_ids = make_batch(2)
    monkeypatch.setattr("app.services.record_event", lambda *args, **kwargs: None)
    with SessionLocal() as session:
        process_document(session, document_ids[0])

    def fail(*args, **kwargs):
        raise RuntimeError("extractor unavailable")

    monkeypatch.setattr("app.services.extract_values", fail)
    with SessionLocal() as session:
        with pytest.raises(RuntimeError, match="extractor unavailable"):
            process_document(session, document_ids[1])
        batch = session.get(Batch, batch_id)
        assert batch.status == "partial_failed"


def test_retry_events_and_timeout_policy(monkeypatch):
    events = []
    monkeypatch.setattr("app.tasks.record_event", lambda event_type, **payload: events.append((event_type, payload)))
    monkeypatch.setattr("app.services.process_document", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("temporary")))
    extract_document.push_request(retries=0)
    try:
        with pytest.raises(OSError, match="temporary"):
            extract_document.run("document-id")
    finally:
        extract_document.request_stack.pop()
    assert [event[0] for event in events] == ["document_processing_attempt", "document_processing_retry_scheduled"]
    assert events[1][1]["next_attempt"] == 2

    events.clear()
    extract_document.push_request(retries=3)
    try:
        with pytest.raises(OSError, match="temporary"):
            extract_document.run("document-id")
    finally:
        extract_document.request_stack.pop()
    assert events[-1][0] == "document_processing_retry_exhausted"
    assert events[-1][1]["next_attempt"] is None
    assert extract_document.retry_kwargs["max_retries"] == 3
    assert extract_document.soft_time_limit == 110
    assert extract_document.time_limit == 120
