# Contract Processing — Delivery Checklist

Legend: `[x]` complete, `[~]` implemented but needs environment verification, `[ ]` not started.

## Shared foundation

- [x] Project plan and implementation boundaries
- [x] Virtual-environment policy: no global project dependencies
- [x] Shared processing design: batches, documents, findings, review states
- [x] ZIP security rules and assignment limits in Django implementation
- [x] Shared OpenAPI contract and cross-framework contract test suite
- [x] Alembic migrations for FastAPI and Flask, applied before API/worker startup
- [x] Short architecture/design document
- [x] Assumptions, trade-offs, and known limitations document
- [x] Production-issue causes and remediation report/table

## Django + DRF

- [x] Isolated `.venv` and declared dependencies
- [x] Batch upload, document tracking, mocked extraction, and finding review API
- [x] PostgreSQL/Redis/Celery/MongoDB/Azure-storage-ready configuration
- [x] Docker Compose services and local environment template
- [x] Docker Compose configuration: API, worker, PostgreSQL, Redis, MongoDB, and Keycloak (all three stacks started successfully)
- [x] Unit/integration tests for upload, processing, review, unsafe ZIP paths, 1,000-document rejection, task idempotency, and wrong-role access
- [x] Decision-focused implementation comments
- [x] Live end-to-end smoke test with real Keycloak token, PostgreSQL, Redis/Celery, MongoDB audit event, upload, and review (passed for Django, FastAPI, and Flask)
- [x] OpenAPI schema, Swagger UI, ReDoc, and endpoint descriptions (shared contract is checked in and all API containers started successfully)
- [~] Failure-path tests: malformed ZIP, duplicate delivery, 1,000-file limit, exact 15 MiB boundary, retries/timeouts, retry exhaustion, and partial failure are covered; concurrent review coverage requires PostgreSQL
- [x] Keycloak OIDC integration, local realm, and role enforcement

## FastAPI

- [x] Create isolated `uv`-managed project environment and install dependencies
- [x] Implement the equivalent API and SQLAlchemy data model
- [x] Add Celery worker, PostgreSQL, Redis, MongoDB, local/Azure Blob storage, Keycloak, Sentry, and Datadog configuration
- [x] Run framework-specific and shared contract tests (8 tests passed; PostgreSQL-only concurrency test is skipped on SQLite)
- [x] Add decision-focused comments and framework notes
- [~] Build and smoke-test the container locally (Docker configuration added; daemon access is blocked here)

## Flask

- [x] Create isolated project virtual environment and install dependencies
- [x] Implement the equivalent API and SQLAlchemy data model
- [x] Add Celery worker, PostgreSQL, Redis, MongoDB, local/Azure Blob storage, Keycloak, Sentry, and Datadog configuration
- [x] Run framework-specific and shared contract tests (8 tests passed; PostgreSQL-only concurrency test is skipped on SQLite)
- [x] Add decision-focused comments and framework notes
- [~] Build and smoke-test the container locally (Docker configuration added; daemon access is blocked here)

## Authentication and authorization

- [x] Choose Keycloak as the shared identity provider for all three implementations
- [x] Add Keycloak to local Docker Compose with an importable development realm
- [x] Define `submitter`, `reviewer`, and `administrator` realm roles
- [x] Protect write and review endpoints with OIDC bearer-token validation
- [x] Record authenticated subject ID and reviewer display name in review/audit records
- [~] Add unauthorized, wrong-role, and valid-role integration tests (wrong-role test is present; live-token coverage awaits smoke-test execution)
- [ ] Configure production Keycloak hosting, realm secrets, redirect URIs, and backup/upgrade procedure

## Deployment and operations

- [ ] Build versioned Docker images in Azure Container Registry
- [ ] Provision low-cost Azure resource group, Container Apps environment, Blob Storage, PostgreSQL, Redis, Key Vault, and Log Analytics
- [ ] Deploy API and worker Container Apps for Django, then FastAPI and Flask
- [ ] Configure per-service managed identity and Key Vault secret access
- [ ] Configure Azure Blob Storage for document files and lifecycle cleanup
- [ ] Configure KEDA/Redis worker scaling, concurrency, retries, and replica-cost caps
- [ ] Configure Sentry DSNs, releases, and error-alert routing
- [ ] Configure Datadog logs, traces, metrics, queue/batch dashboards, and alerts
- [ ] Create Azure budget alerts at $25, $50, $75, and $90
- [ ] Bind `django`, `fastapi`, and `flask` subdomains via Namecheap or Name.com DNS and TLS
- [ ] Run deployed upload-to-review smoke tests and document rollback/teardown steps

## Recommended order

1. Run the Django live smoke test and verify MongoDB audit events/logs.
2. Complete shared design, assumptions, comparison, and incident documents.
3. Restore Docker access and run the live Keycloak/Celery/PostgreSQL/Redis/Mongo workflow for all three APIs.
4. Deploy Django first as the Azure reference deployment.
5. Deploy FastAPI and Flask against the shared contract and migration pattern.
