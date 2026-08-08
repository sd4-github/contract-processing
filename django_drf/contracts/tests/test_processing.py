from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import TestCase

from contracts.models import Batch, ContractDocument, Finding
from contracts.services import process_document
from contracts.tasks import extract_document


class ProcessingFailureTests(TestCase):
    def make_batch(self, document_count=2):
        batch = Batch.objects.create(variables=["effective_date"])
        documents = []
        for number in range(document_count):
            document = ContractDocument.objects.create(
                batch=batch,
                original_filename=f"contract-{number}.txt",
                content=ContentFile(b"text", name=f"contract-{number}.txt"),
                size_bytes=4,
            )
            documents.append(document)
        return batch, documents

    @patch("contracts.services.record_event")
    def test_partial_failure_aggregates_batch_status(self, audit):
        batch, documents = self.make_batch()
        process_document(documents[0].id)

        with patch("contracts.services.extract_values", side_effect=RuntimeError("extractor unavailable")):
            with self.assertRaisesRegex(RuntimeError, "extractor unavailable"):
                process_document(documents[1].id)

        batch.refresh_from_db()
        self.assertEqual(batch.status, Batch.Status.PARTIAL_FAILED)
        self.assertEqual(Finding.objects.filter(document=documents[0]).count(), 1)

    @patch("contracts.tasks.record_event")
    @patch("contracts.tasks.process_document", side_effect=OSError("temporary"))
    def test_retry_events_and_timeout_policy(self, process, audit):
        extract_document.push_request(retries=0)
        try:
            with self.assertRaisesRegex(OSError, "temporary"):
                extract_document.run("document-id")
        finally:
            extract_document.request_stack.pop()
        self.assertEqual(
            [call.args[0] for call in audit.call_args_list],
            ["document_processing_attempt", "document_processing_retry_scheduled"],
        )
        self.assertEqual(audit.call_args_list[1].kwargs["next_attempt"], 2)

        audit.reset_mock()
        extract_document.push_request(retries=3)
        try:
            with self.assertRaisesRegex(OSError, "temporary"):
                extract_document.run("document-id")
        finally:
            extract_document.request_stack.pop()
        self.assertEqual(audit.call_args_list[-1].args[0], "document_processing_retry_exhausted")
        self.assertIsNone(audit.call_args_list[-1].kwargs["next_attempt"])
        self.assertEqual(extract_document.retry_kwargs["max_retries"], 3)
        self.assertEqual(extract_document.soft_time_limit, 110)
        self.assertEqual(extract_document.time_limit, 120)
