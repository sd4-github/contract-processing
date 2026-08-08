# FastAPI implementation

FastAPI is the second equivalent implementation of the contract-processing API.
It uses SQLAlchemy/PostgreSQL as the transactional store, Redis/Celery for
asynchronous extraction, MongoDB-ready configuration, and Keycloak JWT roles.

```bash
uv sync
uv run alembic upgrade head
uv run pytest
cp .env.example .env
docker compose up --build
```

The API is exposed at `http://localhost:8002/api/`; OpenAPI and Swagger UI are
available from FastAPI at `/openapi.json` and `/docs`. The compose file shares
the local development Keycloak realm definition with Django but runs it on 8082.

The Compose `migrate` service applies the reviewed Alembic revisions before the
API and worker start. Local non-Compose runs must apply `alembic upgrade head`
against the configured `DATABASE_URL` first. Uploaded bytes use local `media/`
unless `AZURE_STORAGE_CONNECTION_STRING` or `AZURE_STORAGE_ACCOUNT_URL` is set.
Sentry is enabled by `SENTRY_DSN`; Datadog tracing is opt-in with
`DD_TRACE_ENABLED=true` and the `DD_*` settings in `.env.example`.

The shared behavioral contract runner lives in `../contract_tests/suite.py` and
is exercised by `tests/test_contract.py`.
