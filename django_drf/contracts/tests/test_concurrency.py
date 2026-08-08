import os
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from contracts.models import Batch, ContractDocument, Finding
from contracts.services import process_document


@skipUnless(os.getenv("POSTGRES_HOST"), "concurrent row-lock coverage requires PostgreSQL")
class ConcurrentReviewTests(TransactionTestCase):
    reset_sequences = True

    @patch("contracts.views.record_event")
    @patch("contracts.services.record_event")
    def test_concurrent_reviews_are_serialized(self, service_audit, view_audit):
        batch = Batch.objects.create(variables=["effective_date"])
        document = ContractDocument.objects.create(
            batch=batch,
            original_filename="contract.txt",
            content=ContentFile(b"text", name="contract.txt"),
            size_bytes=4,
        )
        process_document(document.id)
        finding_id = str(Finding.objects.get(document=document).id)

        def review(name):
            client = APIClient()
            response = client.patch(
                f"/api/findings/{finding_id}/review/",
                {"decision": "accepted", "reviewer_name": name},
                format="json",
            )
            return response.status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(review, ("Asha", "Ravi")))
        self.assertEqual(statuses, [200, 200])
