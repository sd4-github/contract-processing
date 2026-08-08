from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import core
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Batch, ContractDocument, Finding
from app.services import process_document
from app.storage import document_storage


pytestmark = pytest.mark.skipif(
    core.DATABASE_URL.startswith("sqlite"),
    reason="concurrent row-lock coverage requires PostgreSQL",
)


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_concurrent_reviews_are_serialized(monkeypatch):
    monkeypatch.setattr("app.main.record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.record_event", lambda *args, **kwargs: None)
    with SessionLocal() as session:
        batch = Batch(variables=["effective_date"])
        session.add(batch)
        session.flush()
        document = ContractDocument(
            batch_id=batch.id,
            original_filename="contract.txt",
            storage_name=f"concurrent-{batch.id}.txt",
            size_bytes=4,
        )
        session.add(document)
        session.flush()
        document_storage.save(document.storage_name, b"text")
        session.commit()
        process_document(session, document.id)
        finding = session.scalar(Finding.__table__.select().where(Finding.document_id == document.id))
        finding_id = finding.id

    def review(name):
        with TestClient(app) as client:
            return client.patch(
                f"/api/findings/{finding_id}/review/",
                json={"decision": "accepted", "reviewer_name": name},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(review, ("Asha", "Ravi")))
    assert statuses == [200, 200]
