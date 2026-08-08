# Local validation and deployment runbook

Use this runbook to validate the three implementations locally, then follow
the linked production sequence. It does not require Kubernetes: the intended
deployment target is Azure Container Apps.

## Local prerequisites

1. Install Docker Engine and the Docker Compose plugin.
2. Confirm the current shell can use Docker:

   ```bash
   docker info
   docker compose version
   ```

   If the account was just added to the `docker` group, start a new login
   session or run `newgrp docker`. Do not make `/var/run/docker.sock`
   world-writable.
3. Run only one framework stack per published host port. Django uses API/Keycloak
   ports `8000`/`8081`, FastAPI uses `8002`/`8082`, and Flask uses `8003`/`8083`.

The Keycloak realm contains development-only users: `submitter` / `Submit123!`,
`reviewer` / `Review123!`, and `administrator` / `Admin123!`. Never deploy these
accounts or passwords.

## Run the local workflows

### Django (reference workflow)

```bash
cd django_drf
cp .env.example .env   # first run only
docker compose up --build -d
bash scripts/smoke_test.sh
```

Expected result: `PASS: authenticated upload, Celery extraction, batch
tracking, and reviewer acceptance succeeded.`

Detailed diagnostics: [live-django-workflow.md](live-django-workflow.md).

### FastAPI

```bash
cd fastapi
uv sync
uv run pytest
cp .env.example .env   # first run only
docker compose up --build -d
curl --fail http://localhost:8002/api/health/
```

Follow the authenticated upload and review commands in
[live-fastapi-workflow.md](live-fastapi-workflow.md). A successful run has a
completed batch/document and an accepted finding.

### Flask

```bash
cd flask
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
cp .env.example .env   # first run only
docker compose up --build -d
curl --fail http://localhost:8003/api/health/
```

Follow the authenticated upload and review commands in
[live-flask-workflow.md](live-flask-workflow.md). A successful run has a
completed batch/document and an accepted finding.

## Validate backing services

In the framework directory after a successful workflow:

```bash
docker compose logs --tail=150 worker
docker compose exec postgres psql -U contracts -d contracts -c 'select id, status, completed_at from batches;'
docker compose exec redis redis-cli ping
docker compose exec mongodb mongosh --quiet contract_processing --eval 'db.events.find({}, {event_type:1, occurred_at:1, _id:0}).sort({occurred_at:1}).toArray()'
```

Django uses `contracts_batch` rather than `batches` for the batch table. The
expected Redis result is `PONG`; MongoDB should show batch, processing,
completion, and review audit events.

## Cleanup

```bash
docker compose down
```

This preserves local database volumes. Use `docker compose down -v` only when
you intentionally want to discard all local PostgreSQL and MongoDB test data.

## Production deployment workflow

1. Run the contract suite and all three local workflows above; record results.
2. Provision Azure with Bicep (recommended) or Terraform/OpenTofu: resource
   group, ACR, Container Apps environment, PostgreSQL, Redis, Blob Storage,
   Key Vault, Log Analytics, and monitoring alerts.
3. Create the production Keycloak realm/client, roles, HTTPS redirect URIs,
   signing-key rotation, backups, and administrator controls. Do not reuse the
   local realm fixture.
4. Create a separate managed identity per API and worker. Grant only required
   Key Vault and Blob Storage roles.
5. Build API and worker images, scan them, tag with the Git commit SHA, push to
   ACR, and retain a previous immutable image for rollback.
6. Run Alembic migrations as a controlled release job. Deploy Django API and
   worker as separate Container Apps, with public ingress only for the API.
7. Configure secrets, health probes, KEDA Redis worker scaling, Sentry/Datadog,
   Azure Monitor alerts, custom DNS, and TLS.
8. Execute the authenticated upload-to-review workflow against staging. Promote
   only after health, task, error-rate, and queue metrics are healthy.
9. Repeat for FastAPI and Flask with isolated app names, revisions, and
   subdomains. Use revision traffic splitting and roll back by routing to the
   prior immutable revision.

The detailed Azure checklist, operations, rollback, budget, and teardown steps
are in [deployment-plan.md](deployment-plan.md).
