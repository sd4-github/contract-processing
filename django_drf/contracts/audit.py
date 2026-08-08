import logging
from datetime import datetime, timezone

from django.conf import settings

logger = logging.getLogger(__name__)


def record_event(event_type: str, **payload) -> None:
    """Write immutable operational events without coupling API availability to MongoDB."""
    try:
        from pymongo import MongoClient

        client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=1000)
        client[settings.MONGO_DATABASE].events.insert_one({
            "event_type": event_type,
            "occurred_at": datetime.now(timezone.utc),
            **payload,
        })
        client.close()
    except Exception:
        # Audit delivery is observable and can be retried later; it must not roll back contract data.
        logger.exception("Could not write audit event", extra={"event_type": event_type})
