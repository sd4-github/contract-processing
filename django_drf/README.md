# Django + DRF contract-processing prototype

This is the first of three equivalent implementations. It accepts a ZIP of contract files, queues one asynchronous extraction task per document, stores mocked findings, and exposes reviewer actions.

## Environment policy

Never install this project's dependencies globally. Django commands must use this directory's `.venv`; the later FastAPI implementation will use its own `uv`-managed environment, and Flask will have its own virtual environment.

## Local stack

The Compose stack runs Django/DRF, Celery, PostgreSQL, Redis, MongoDB, and Keycloak. PostgreSQL stores transactional data; MongoDB stores append-only operational audit events. Keycloak protects submission and review endpoints with OIDC bearer tokens.

```bash
cp .env.example .env
docker compose up --build
```

For a non-container command such as running tests, activate the isolated environment first:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python manage.py test
```

Open `http://localhost:8000/api/health/`. API requests are made to `http://localhost:8000/api/`.

Interactive API documentation is available at `http://localhost:8000/api/docs/`; the raw OpenAPI schema is at `/api/schema/`, and ReDoc is at `/api/redoc/`.

Keycloak is available at `http://localhost:8081` for local development. The imported development realm has `submitter` / `Submit123!`, `reviewer` / `Review123!`, and `administrator` / `Admin123!` accounts. These credentials are deliberately local-only and must be replaced before any deployment.

Get a submitter token, then use it in API calls:

```bash
TOKEN=$(curl -sS -X POST http://localhost:8081/realms/contract-processing/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=contract-processing-api&grant_type=password&username=submitter&password=Submit123!' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

## API workflow

```bash
curl -X POST http://localhost:8000/api/batches/ \
  -H "Authorization: Bearer $TOKEN" \
  -F 'zip_file=@contracts.zip' \
  -F 'variables=["effective_date", "monthly_rent", "governing_law"]'
```

Use the returned batch ID with `GET /api/batches/{batch_id}/`. Each document contains its findings. Review an individual finding:

```bash
curl -X PATCH http://localhost:8000/api/findings/{finding_id}/review/ \
  -H "Authorization: Bearer $REVIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"accepted","reviewer_name":"Asha"}'
```

## Tests

With dependencies installed, run:

```bash
python manage.py test
```

## Full Compose smoke test

After `sudo docker compose up --build -d` reports all services as running, execute this from the host terminal (no virtual environment activation is required):

```bash
bash scripts/smoke_test.sh
```

It obtains real local Keycloak tokens, uploads a ZIP as a submitter, waits for the Celery worker, then accepts a generated finding as a reviewer.

## Current safeguards

- ZIP members are never extracted to disk, unsafe paths are rejected, and each document is limited to 15 MB.
- A batch permits at most 1,000 documents.
- Finding writes are idempotent through a unique document/variable constraint.
- Batch state is recalculated from document state inside a transaction.
- Celery uses late acknowledgements, one prefetched task, task time limits, and retryable task configuration.
- Keycloak realm roles enforce `submitter`, `reviewer`, and `administrator` access when `AUTH_ENABLED=true`.
- In Compose, external token issuer validation uses `localhost` while JWKS resolution uses the internal Keycloak service address.

Azure Blob Storage, Sentry, Datadog, and production secrets are configuration-driven. Enable the optional Datadog Agent locally with `DD_API_KEY=... docker compose --profile observability up --build`.
