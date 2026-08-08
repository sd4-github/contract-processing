import io
import json
import zipfile

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.tasks import extract_document


def archive(*files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as value:
        for name, content in files:
            value.writestr(name, content)
    return output.getvalue()


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_upload_process_and_review(monkeypatch):
    # Unit tests run task code explicitly; production publishes to Celery only
    # after the upload transaction commits.
    queued = []
    monkeypatch.setattr(extract_document, "delay", queued.append)
    # Unit tests verify the transactional workflow without waiting for an
    # intentionally best-effort external MongoDB audit sink.
    monkeypatch.setattr("app.main.record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.tasks.record_event", lambda *args, **kwargs: None)
    client = TestClient(app)
    response = client.post("/api/batches/", files={"zip_file": ("contracts.zip", archive(("agreement.txt", b"text")), "application/zip")}, data={"variables": json.dumps(["effective_date", "monthly_rent"])})
    assert response.status_code == 202
    assert len(queued) == 1
    extract_document.run(queued[0])
    batch = client.get(f"/api/batches/{response.json()['id']}/").json()
    assert batch["status"] == "completed"
    finding = batch["documents"][0]["findings"][0]
    review = client.patch(f"/api/findings/{finding['id']}/review/", json={"decision": "accepted", "reviewer_name": "Asha"})
    assert review.status_code == 200 and review.json()["review_status"] == "accepted"


def test_rejects_unsafe_zip():
    client = TestClient(app)
    response = client.post("/api/batches/", files={"zip_file": ("unsafe.zip", archive(("../secret.txt", b"x")), "application/zip")}, data={"variables": '["effective_date"]'})
    assert response.status_code == 400
