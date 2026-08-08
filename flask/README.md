# Flask implementation

Flask is the third equivalent implementation of the contract-processing API.
It keeps the same asynchronous batch workflow, SQLAlchemy/PostgreSQL data
model, Celery/Redis worker semantics, and Keycloak role boundaries.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
pytest
cp .env.example .env
docker compose up --build
```

The API runs at `http://localhost:8003/api/`. Flask intentionally does not
generate OpenAPI automatically; its endpoints must be exercised by the shared
contract suite in `../contract_tests/suite.py`, which is wired into
`tests/test_contract.py`.

The Compose `migrate` service applies the reviewed Alembic revisions before the
API and worker start. Uploaded bytes use local `media/` unless
`AZURE_STORAGE_CONNECTION_STRING` or `AZURE_STORAGE_ACCOUNT_URL` is set.
Sentry is enabled by `SENTRY_DSN`; Datadog tracing is opt-in with
`DD_TRACE_ENABLED=true` and the `DD_*` settings in `.env.example`.
