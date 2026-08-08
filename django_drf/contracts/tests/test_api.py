import io
import json
import zipfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient

from contracts.authentication import KeycloakUser
from contracts.models import Batch, Finding
from contracts.services import process_document


def make_zip(*files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in files:
            archive.writestr(name, content)
    return output.getvalue()


class BatchApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("contracts.views.record_event")
    @patch("contracts.views.extract_document.delay")
    def test_upload_then_process_and_review(self, delay, audit):
        # Production enqueues only after commit; TestCase wraps tests in a transaction, so execute the callback here.
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/batches/",
                {"zip_file": SimpleUploadedFile("contracts.zip", make_zip(("agreement.pdf", b"contract text")), content_type="application/zip"), "variables": json.dumps(["effective_date", "monthly_rent"])},
                format="multipart",
            )
        self.assertEqual(response.status_code, 202)
        batch = Batch.objects.get(id=response.data["id"])
        self.assertEqual(batch.documents.count(), 1)
        delay.assert_called_once()

        with patch("contracts.services.record_event"):
            process_document(batch.documents.get().id)
        batch.refresh_from_db()
        self.assertEqual(batch.status, Batch.Status.COMPLETED)
        finding = Finding.objects.get(variable_name="monthly_rent")
        review = self.client.patch(f"/api/findings/{finding.id}/review/", {"decision": "accepted", "reviewer_name": "Asha"}, format="json")
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.data["review_status"], "accepted")

    def test_rejects_unsafe_zip_path(self):
        response = self.client.post(
            "/api/batches/",
            {"zip_file": SimpleUploadedFile("unsafe.zip", make_zip(("../secret.pdf", b"x")), content_type="application/zip"), "variables": json.dumps(["effective_date"])},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Batch.objects.count(), 0)

    def test_rejects_more_than_one_thousand_documents(self):
        archive = make_zip(*[(f"contract-{number}.txt", b"x") for number in range(1001)])
        response = self.client.post(
            "/api/batches/",
            {"zip_file": SimpleUploadedFile("large.zip", archive, content_type="application/zip"), "variables": json.dumps(["effective_date"])},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Batch.objects.count(), 0)

    @patch("contracts.services.record_event")
    def test_repeated_processing_does_not_duplicate_findings(self, audit):
        batch = Batch.objects.create(variables=["effective_date"])
        document = batch.documents.create(original_filename="agreement.txt", content=SimpleUploadedFile("agreement.txt", b"text"), size_bytes=4)
        process_document(document.id)
        process_document(document.id)
        self.assertEqual(Finding.objects.filter(document=document).count(), 1)

    @override_settings(AUTH_ENABLED=True)
    def test_keycloak_roles_restrict_submission(self):
        reviewer = APIClient()
        reviewer.force_authenticate(user=KeycloakUser({"sub": "reviewer-id", "realm_access": {"roles": ["reviewer"]}}))
        response = reviewer.post(
            "/api/batches/",
            {"zip_file": SimpleUploadedFile("contracts.zip", make_zip(("agreement.pdf", b"text")), content_type="application/zip"), "variables": json.dumps(["effective_date"])},
            format="multipart",
        )
        self.assertEqual(response.status_code, 403)
