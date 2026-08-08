import json
import sys
from unittest.mock import patch
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from contracts.services import process_document
from contract_tests.suite import ContractResponse, run_contract_suite


class DjangoContractAdapter:
    def __init__(self, test_case, client, queued):
        self.test_case = test_case
        self.client = client
        self.queued = queued

    def health(self):
        response = self.client.get("/api/health/")
        return ContractResponse(response.status_code, response.data)

    def upload(self, archive, variables, filename="contracts.zip"):
        response = self.client.post(
            "/api/batches/",
            {
                "zip_file": SimpleUploadedFile(filename, archive, content_type="application/zip"),
                "variables": json.dumps(variables),
            },
            format="multipart",
        )
        return ContractResponse(response.status_code, response.data)

    def get_batch(self, batch_id):
        response = self.client.get(f"/api/batches/{batch_id}/")
        return ContractResponse(response.status_code, response.data)

    def get_document(self, document_id):
        response = self.client.get(f"/api/documents/{document_id}/")
        return ContractResponse(response.status_code, response.data)

    def review(self, finding_id, decision, reviewer_name):
        response = self.client.patch(
            f"/api/findings/{finding_id}/review/",
            {"decision": decision, "reviewer_name": reviewer_name},
            format="json",
        )
        return ContractResponse(response.status_code, response.data)

    def drain_queue(self):
        while self.queued:
            process_document(self.queued.pop(0))


class SharedApiContractTests(TransactionTestCase):
    reset_sequences = True

    @patch("contracts.views.record_event")
    @patch("contracts.services.record_event")
    @patch("contracts.tasks.record_event")
    @patch("contracts.views.extract_document.delay")
    def test_shared_api_contract(self, delay, task_audit, service_audit, view_audit):
        queued = []
        delay.side_effect = queued.append
        adapter = DjangoContractAdapter(self, APIClient(), queued)
        run_contract_suite(adapter)
