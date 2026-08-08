import io
import json
import zipfile

from app.database import Base, engine
from app.main import app
from app.tasks import extract_document


def archive(*files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as value:
        for name, content in files: value.writestr(name, content)
    return output.getvalue()


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_upload_process_and_review(monkeypatch):
    queued = []
    monkeypatch.setattr(extract_document, "delay", queued.append)
    monkeypatch.setattr("app.main.record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.tasks.record_event", lambda *args, **kwargs: None)
    client = app.test_client()
    response = client.post("/api/batches/", data={"zip_file": (io.BytesIO(archive(("agreement.txt", b"text"))), "contracts.zip"), "variables": json.dumps(["effective_date", "monthly_rent"])}, content_type="multipart/form-data")
    assert response.status_code == 202 and len(queued) == 1
    extract_document.run(queued[0])
    batch = client.get(f"/api/batches/{response.json['id']}/").json
    assert batch["status"] == "completed"
    response = client.patch(f"/api/findings/{batch['documents'][0]['findings'][0]['id']}/review/", json={"decision": "accepted", "reviewer_name": "Asha"})
    assert response.status_code == 200 and response.json["review_status"] == "accepted"


def test_rejects_unsafe_zip():
    response = app.test_client().post("/api/batches/", data={"zip_file": (io.BytesIO(archive(("../secret.txt", b"x"))), "unsafe.zip"), "variables": '["effective_date"]'}, content_type="multipart/form-data")
    assert response.status_code == 400
