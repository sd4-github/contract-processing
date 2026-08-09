import logging
from datetime import datetime, timezone

from pymongo import MongoClient

from .core import MONGO_DATABASE, MONGO_URI

logger = logging.getLogger(__name__)

# Instantiate globally to leverage connection pooling.
# PyMongo handles thread safety and connection lifecycles automatically.
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1000)
audit_collection = mongo_client[MONGO_DATABASE].events

def record_event(event_type: str, **payload):
    """MongoDB is append-only operational telemetry, not the transactional source of truth."""
    try:
        audit_collection.insert_one({
            "event_type": event_type, 
            "occurred_at": datetime.now(timezone.utc), 
            **payload
        })
    except Exception:
        # Audit delivery is observable but must not block the main execution flow.
        logger.exception("Could not write audit event", extra={"event_type": event_type})