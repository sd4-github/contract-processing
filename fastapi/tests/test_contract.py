import json

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.tasks import extract_document
from contract_tests.suite import ContractResponse, run_contract_suite


def setup_module():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def test_shared_api_contract(monkeypatch):
    queued = []
    monkeypatch.setattr(extract_document, "delay", queued.append)
    monkeypatch.setattr("app.main.record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.record_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.tasks.record_event", lambda *args, **kwargs: None)
    client = TestClient(app)

    class Adapter:
        def health(self):
            response = client.get("/api/health/")
            return ContractResponse(response.status_code, response.json())

        def upload(self, archive, variables, filename="contracts.zip"):
            response = client.post(
                "/api/batches/",
                files={"zip_file": (filename, archive, "application/zip")},
                data={"variables": json.dumps(variables)},
            )
            return ContractResponse(response.status_code, response.json())

        def get_batch(self, batch_id):
            response = client.get(f"/api/batches/{batch_id}/")
            return ContractResponse(response.status_code, response.json())

        def get_document(self, document_id):
            response = client.get(f"/api/documents/{document_id}/")
            return ContractResponse(response.status_code, response.json())

        def review(self, finding_id, decision, reviewer_name):
            response = client.patch(
                f"/api/findings/{finding_id}/review/",
                json={"decision": decision, "reviewer_name": reviewer_name},
            )
            return ContractResponse(response.status_code, response.json())

        def drain_queue(self):
            while queued:
                extract_document.run(queued.pop(0))

    run_contract_suite(Adapter())
