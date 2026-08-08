from django.db import transaction
from django.utils import timezone

from .audit import record_event
from .extraction import extract_values
from .models import Batch, ContractDocument, Finding


def refresh_batch_status(batch_id) -> None:
    # Lock the aggregate row while deriving its state so concurrent workers cannot publish stale statuses.
    with transaction.atomic():
        batch = Batch.objects.select_for_update().get(id=batch_id)
        statuses = list(batch.documents.values_list("status", flat=True))
        if not statuses or any(status == ContractDocument.Status.PROCESSING for status in statuses):
            status = Batch.Status.PROCESSING
        elif any(status == ContractDocument.Status.PENDING for status in statuses):
            status = Batch.Status.PENDING
        elif all(status == ContractDocument.Status.COMPLETED for status in statuses):
            status = Batch.Status.COMPLETED
        elif all(status == ContractDocument.Status.FAILED for status in statuses):
            status = Batch.Status.FAILED
        else:
            status = Batch.Status.PARTIAL_FAILED
        batch.status = status
        if status in {Batch.Status.COMPLETED, Batch.Status.FAILED, Batch.Status.PARTIAL_FAILED}:
            batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "completed_at"])


def process_document(document_id) -> None:
    # The status check is the idempotency guard for at-least-once message delivery.
    with transaction.atomic():
        document = ContractDocument.objects.select_for_update().select_related("batch").get(id=document_id)
        if document.status == ContractDocument.Status.COMPLETED:
            return
        document.status = ContractDocument.Status.PROCESSING
        document.error_message = ""
        document.save(update_fields=["status", "error_message"])
        record_event("document_processing_started", batch_id=str(document.batch_id), document_id=str(document.id))

    try:
        with document.content.open("rb") as file_handle:
            values = extract_values(file_handle.read(), document.batch.variables)
        with transaction.atomic():
            document = ContractDocument.objects.select_for_update().select_related("batch").get(id=document_id)
            # update_or_create complements the database constraint when a task is retried after a partial write.
            for variable_name, extracted_value in values.items():
                Finding.objects.update_or_create(
                    document=document,
                    variable_name=variable_name,
                    defaults={"extracted_value": extracted_value},
                )
            document.status = ContractDocument.Status.COMPLETED
            document.processed_at = timezone.now()
            document.save(update_fields=["status", "processed_at"])
        record_event("document_processing_completed", batch_id=str(document.batch_id), document_id=str(document.id))
    except Exception as exc:
        ContractDocument.objects.filter(id=document_id).update(status=ContractDocument.Status.FAILED, error_message=str(exc)[:2000])
        record_event("document_processing_failed", document_id=str(document_id), error=str(exc))
        raise
    finally:
        # Every terminal outcome recomputes the batch from document records rather than incrementing counters.
        refresh_batch_status(document.batch_id)
