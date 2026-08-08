from django.conf import settings
from celery import shared_task

from .audit import record_event
from .services import process_document


@shared_task(
    bind=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": settings.CELERY_MAX_RETRIES},
    soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.CELERY_TASK_TIME_LIMIT,
)
def extract_document(self, document_id: str) -> None:
    # Only transient I/O failures retry automatically; malformed documents remain visible as failed work.
    attempt = self.request.retries + 1
    record_event(
        "document_processing_attempt",
        document_id=str(document_id),
        attempt=attempt,
        max_retries=settings.CELERY_MAX_RETRIES,
    )
    try:
        process_document(document_id)
    except OSError as exc:
        exhausted = self.request.retries >= settings.CELERY_MAX_RETRIES
        record_event(
            "document_processing_retry_exhausted" if exhausted else "document_processing_retry_scheduled",
            document_id=str(document_id),
            attempt=attempt,
            next_attempt=None if exhausted else attempt + 1,
            error=str(exc)[:2000],
        )
        raise
