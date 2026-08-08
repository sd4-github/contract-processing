import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = "local-development-only-change-before-deployment"
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "contracts",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
# The same settings module supports containerized PostgreSQL and a zero-setup local exploration mode.
if os.getenv("POSTGRES_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "contracts"),
        "USER": os.getenv("POSTGRES_USER", "contracts"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "contracts"),
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }}
else:
    # SQLite keeps the API explorable without containers; Compose uses PostgreSQL by default.
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {"DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer"]}

# Compose enables OIDC; disabling it is restricted to standalone local exploration and test execution.
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8081")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "contract-processing")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "contract-processing-api")
KEYCLOAK_ISSUER = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}"
KEYCLOAK_JWKS_URL = os.getenv("KEYCLOAK_JWKS_URL", f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs")
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = ["contracts.authentication.KeycloakJWTAuthentication"]
REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
SPECTACULAR_SETTINGS = {
    "TITLE": "Contract Processing API",
    "DESCRIPTION": "Bulk contract upload, mocked variable extraction, batch tracking, and reviewer decisions.",
    "VERSION": "1.0.0-local",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}

# Redis database 0 carries work; database 1 isolates task results from queue operations.
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "120"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "110"))
CELERY_MAX_RETRIES = int(os.getenv("CELERY_MAX_RETRIES", "3"))
# Acknowledge only after work finishes and reserve one task per worker so a crash does not strand a batch.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "contract_processing")

# Switching storage through configuration lets deployed workers share Blob Storage without changing models.
if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
    STORAGES = {
        "default": {"BACKEND": "storages.backends.azure_storage.AzureStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    AZURE_CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    AZURE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "contract-documents")

# Sentry remains opt-in locally, avoiding accidental event delivery from a developer machine.
if sentry_dsn := os.getenv("SENTRY_DSN"):
    import sentry_sdk
    sentry_sdk.init(dsn=sentry_dsn, traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")))
