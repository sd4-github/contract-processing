# Deployment plan

Deploy each framework as two Azure Container Apps: one public API and one
internal Celery worker. Kubernetes is not required. Deploy Django first, then
FastAPI and Flask only after the preceding deployment passes its staging smoke
test.

## Shared foundation — do once

1. Create one Azure resource group, Container Apps environment, ACR, Key Vault,
   Log Analytics/Application Insights, PostgreSQL, Redis, Blob Storage, and a
   managed Mongo-compatible audit store.
2. Create a production Keycloak realm and client. Define `submitter`,
   `reviewer`, and `administrator`; configure HTTPS redirect URIs, signing-key
   rotation, backups, and administrator access. Never import the local realm or
   development passwords.
3. Add secrets to Key Vault: database URL, Redis URL, MongoDB URI, Keycloak
   issuer/client/JWKS values, Blob settings, Sentry DSN, and Datadog key.
4. Create one managed identity for every API and worker. Give it only `Key Vault
   Secrets User` and the Blob data role it needs; grant ACR pull access to the
   apps.
5. Configure budget alerts, database backups/PITR, Redis capacity alerts, Blob
   retention rules, API error alerts, queue-depth alerts, and worker-failure
   alerts.

For every release: run tests and the local workflow, build API and worker
images, scan them, tag them with the commit SHA, push to ACR, and record the
image digests. Do not deploy `latest`.

## Django deployment

1. Build and push two images from `django_drf/Dockerfile`: `django-api:<sha>`
   and `django-worker:<sha>`.
2. Run `python manage.py migrate` as a one-off controlled release job using the
   production Django environment. Confirm it succeeds before changing API
   traffic.
3. Create `contract-django-api` from `django-api:<sha>`. Set public HTTPS
   ingress, target port `8000`, health path `/api/health/`, and all Key Vault
   configuration values.
4. Create `contract-django-worker` from `django-worker:<sha>` with no ingress.
   Set `celery -A config worker --loglevel=INFO --concurrency=2`, Redis scaling,
   retry/time-limit settings, and a conservative maximum replica count.
5. Bind `django.<domain>` and TLS. Run the authenticated Django smoke test
   against the staging hostname, confirm a completed batch/finding, then inspect
   PostgreSQL, Redis, Mongo audit events, Sentry, and logs.
6. Promote the revision only after those checks pass. Roll back by routing
   traffic to the prior immutable API revision; do not roll back migrations
   without a tested database recovery plan.

## FastAPI deployment

1. Build and push `fastapi-api:<sha>` and `fastapi-worker:<sha>` from
   `fastapi/Dockerfile`.
2. Run `alembic upgrade head` as a one-off release job with the FastAPI
   production environment. It must complete before the API revision is created.
3. Create `contract-fastapi-api` from `fastapi-api:<sha>`, with public HTTPS
   ingress, target port `8000`, health path `/api/health/`, and Key Vault
   configuration values.
4. Create `contract-fastapi-worker` from `fastapi-worker:<sha>` with no ingress.
   Its command is `celery -A app.tasks.celery_app worker --loglevel=INFO
   --concurrency=2`; configure Redis scaling and the worker task limits.
5. Bind `fastapi.<domain>` and TLS. Run the FastAPI authenticated upload,
   polling, and reviewer-acceptance workflow against staging. Verify the same
   database, Redis, Mongo, and telemetry evidence as Django.
6. Promote or roll back using immutable Container Apps revisions exactly as for
   Django.

## Flask deployment

1. Build and push `flask-api:<sha>` and `flask-worker:<sha>` from
   `flask/Dockerfile`.
2. Run `alembic upgrade head` as a one-off release job with the Flask production
   environment.
3. Create `contract-flask-api` from `flask-api:<sha>`, with public HTTPS
   ingress, target port `8000`, health path `/api/health/`, and Key Vault
   configuration values.
4. Create `contract-flask-worker` from `flask-worker:<sha>` with no ingress.
   Its command is `celery -A app.tasks.celery_app worker --loglevel=INFO
   --concurrency=2`; configure Redis scaling and the worker task limits.
5. Bind `flask.<domain>` and TLS. Execute the Flask authenticated upload,
   polling, and reviewer-acceptance workflow against staging; verify data and
   observability evidence.
6. Promote with revision traffic splitting; return traffic to the previous
   immutable revision if health, queue, or error metrics degrade.

## After each deployment

1. Run the checked-in OpenAPI contract suite against the public API.
2. Confirm reviewer RBAC with real production-role test accounts.
3. Record deployed image digests, migration revision, smoke-test batch ID, and
   dashboard links in the release record.
4. Keep the previous image and revision until backup/restore and rollback
   evidence is recorded.
