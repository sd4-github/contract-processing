import logging
from datetime import datetime, timezone

from pymongo import MongoClient

from .core import MONGO_DATABASE, MONGO_URI

logger = logging.getLogger(__name__)


def record_event(event_type: str, **payload) -> None:
    """Audit failure is logged, never allowed to roll back transactional work."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1000)
        client[MONGO_DATABASE].events.insert_one({"event_type": event_type, "occurred_at": datetime.now(timezone.utc), **payload})
        client.close()
    except Exception:
        logger.exception("Could not write audit event", extra={"event_type": event_type})
