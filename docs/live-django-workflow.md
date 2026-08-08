# Live Django workflow validation

This guide verifies the complete local Django reference workflow: Keycloak
authentication, PostgreSQL persistence, Redis/Celery asynchronous work, and
MongoDB audit events.

For deployment after this local workflow is verified, use the
[shared deployment plan](deployment-plan.md).

## Prerequisites

Install Docker Engine with the Compose plugin, then confirm that the current
user can talk to the Docker daemon:

```bash
docker info
docker compose version
```

If `docker info` reports permission denied for `/var/run/docker.sock`, grant
your user access and start a new login session (or run `newgrp docker`):

```bash
sudo usermod -aG docker "$USER"
newgrp docker
docker info
```

Do not solve this by making the Docker socket world-writable. On managed or
remote environments where group membership cannot be changed, run the steps
below from a host account that already has Docker access.

## Start and test

From the repository root:

```bash
cd django_drf
cp .env.example .env       # only needed the first time
docker compose up --build -d
docker compose ps
bash scripts/smoke_test.sh
```

The smoke test obtains local Keycloak tokens, uploads a ZIP as `submitter`,
waits for Celery to process it, and accepts a finding as `reviewer`. It exits
non-zero if any stage fails.

## Verify each component explicitly

```bash
# API and Keycloak availability
curl --fail http://localhost:8000/api/health/
curl --fail http://localhost:8081/realms/contract-processing/.well-known/openid-configuration

# Worker received and completed the document task
docker compose logs --tail=150 worker

# PostgreSQL contains the batch, document, and finding records
docker compose exec postgres psql -U contracts -d contracts -c \
  'select id, status, created_at, completed_at from contracts_batch;'
docker compose exec postgres psql -U contracts -d contracts -c \
  'select original_filename, status, processed_at from contracts_contractdocument;'

# Redis has an accessible broker
docker compose exec redis redis-cli ping

# MongoDB contains the audit lifecycle events
docker compose exec mongodb mongosh --quiet contract_processing --eval \
  'db.events.find({}, {event_type: 1, batch_id: 1, document_id: 1, occurred_at: 1, _id: 0}).sort({occurred_at: 1}).toArray()'
```

For the smoke-test batch, MongoDB should show `batch_created`,
`document_processing_started`, `document_processing_completed`, and
`finding_reviewed`. PostgreSQL should report a `completed` batch/document and
an `accepted` finding.

## Troubleshooting and cleanup

```bash
docker compose logs api worker keycloak postgres redis mongodb
docker compose down                 # stops services, keeps database volumes
docker compose down -v              # also removes local PostgreSQL/Mongo data
```

Use `down -v` only when discarding the local test data is intended.
