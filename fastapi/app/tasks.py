from celery import Celery

from . import core
from .audit import record_event
from .core import REDIS_URL
from .observability import configure as configure_observability

celery_app = Celery("contract_processing_fastapi", broker=REDIS_URL, backend=REDIS_URL.rsplit("/", 1)[0] + "/1")
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=core.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=core.CELERY_TASK_SOFT_TIME_LIMIT,
)
configure_observability()


@celery_app.task(
    bind=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": core.CELERY_MAX_RETRIES},
    soft_time_limit=core.CELERY_TASK_SOFT_TIME_LIMIT,
    time_limit=core.CELERY_TASK_TIME_LIMIT,
)
def extract_document(self, document_id: str) -> None:
    attempt = self.request.retries + 1
    record_event(
        "document_processing_attempt",
        document_id=document_id,
        attempt=attempt,
        max_retries=core.CELERY_MAX_RETRIES,
    )
    from .database import SessionLocal
    from .services import process_document

    try:
        with SessionLocal() as session:
            process_document(session, document_id)
    except OSError as exc:
        exhausted = self.request.retries >= core.CELERY_MAX_RETRIES
        record_event(
            "document_processing_retry_exhausted" if exhausted else "document_processing_retry_scheduled",
            document_id=document_id,
            attempt=attempt,
            next_attempt=None if exhausted else attempt + 1,
            error=str(exc)[:2000],
        )
        raise
