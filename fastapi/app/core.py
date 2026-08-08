import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./contract_processing.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "contract_processing")
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "120"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "110"))
CELERY_MAX_RETRIES = int(os.getenv("CELERY_MAX_RETRIES", "3"))
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8081")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "contract-processing")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "contract-processing-api")
KEYCLOAK_ISSUER = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}"
KEYCLOAK_JWKS_URL = os.getenv("KEYCLOAK_JWKS_URL", f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs")
DOCUMENT_STORAGE = Path(os.getenv("DOCUMENT_STORAGE", "./media"))
DOCUMENT_STORAGE.mkdir(parents=True, exist_ok=True)
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_ACCOUNT_URL = os.getenv("AZURE_STORAGE_ACCOUNT_URL", "")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "contract-documents")
AZURE_STORAGE_PREFIX = os.getenv("AZURE_STORAGE_PREFIX", "")
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "local")
SENTRY_RELEASE = os.getenv("SENTRY_RELEASE", "")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
SENTRY_PROFILES_SAMPLE_RATE = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0"))
DD_SERVICE = os.getenv("DD_SERVICE", "contract-processing-fastapi")
DD_ENV = os.getenv("DD_ENV", "local")
DD_VERSION = os.getenv("DD_VERSION", "local")
DD_AGENT_HOST = os.getenv("DD_AGENT_HOST", "datadog")
DD_TRACE_ENABLED = os.getenv("DD_TRACE_ENABLED", "false").lower() == "true"
DD_LOGS_INJECTION = os.getenv("DD_LOGS_INJECTION", "true").lower() == "true"
MAX_DOCUMENTS = 1_000
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
