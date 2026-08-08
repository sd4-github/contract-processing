# Contract Processing — Learning Project Plan

## Summary

Create three equivalent backend implementations in `/home/soumikd4/Desktop/code/contract-processing/`:

- `fastapi/`, `django/`, and `flask/`
- Shared contract/API specification, test fixtures, Docker tooling, and documentation
- Background ZIP processing for up to 1,000 documents, mocked variable extraction, batch tracking, and reviewer accept/reject actions
- Azure deployments for all three versions, each behind its own custom subdomain
- A complete production-incident case-study report

No code, package, service, database, environment variable, domain, Docker image, or documentation identifier will use the name “Leegality.”

## Architecture and interfaces

- Standardize behavior across all frameworks:
  - Upload a ZIP and an explicit list of extraction variable names.
  - Return a batch ID immediately; process documents asynchronously.
  - Provide batch, document, finding, and review endpoints.
  - Use OpenAPI as the shared API contract; Django will expose REST endpoints rather than server-rendered pages.
- Use PostgreSQL as the source of truth for batches, document metadata, extraction findings, review decisions, idempotency records, and aggregate statuses.
- Use Redis and Celery for queued extraction jobs, retries, visibility into failures, and worker concurrency.
- Use MongoDB for append-only audit/process events: upload accepted, document queued, extraction attempts, retries, completion/failure, and reviewer decisions.
- Keep uploaded ZIPs and unpacked files on local storage for development; Azure Blob Storage becomes the deployed storage layer.
- Enforce ZIP safety and assignment limits: 1,000-document maximum, 15 MB per document, archive path validation, supported-file validation, size checks before processing, and cleanup of temporary files.
- Implement a mocked extraction-provider interface with deterministic seeded results. Use provider timeouts, bounded retries with backoff, idempotency keys, and a dead-letter/failure state.
- Derive batch status from document states transactionally rather than trusting independent worker updates.

## Framework implementations and documentation

- Build each version with comparable modules for API, ORM/data access, Celery tasks, mocked provider, status aggregation, observability, and configuration.
- Use comments only where they explain non-obvious decisions—such as idempotency, retries, locking, ZIP security, transaction boundaries, and framework-specific tradeoffs.
- Add a comparison document explaining Django vs. FastAPI vs. Flask in this system. FastAPI is the reference implementation for design decisions, while all three are deployed for learning.
- Write the required README, setup instructions, API examples, assumptions/trade-offs, known limitations, short design document, and the Part 2 cause-and-remediation table/report.

## Azure, domains, and observability

- Provision one low-cost Azure resource group and Container Apps environment; deploy six Container Apps: API and Celery worker for each framework.
- Use one shared Azure Database for PostgreSQL instance, one small Azure Cache for Redis instance, Azure Blob Storage, Azure Container Registry, Key Vault, and Application Insights/Log Analytics with retention limits.
- Configure public ingress only for the three APIs; workers remain internal with Redis/KEDA scaling and strict replica caps.
- Bind three neutral subdomains such as `fastapi.<domain>`, `django.<domain>`, and `flask.<domain>` through Namecheap or Name.com DNS, with TLS certificates managed through Container Apps or Key Vault.
- Store all credentials in Key Vault/Container Apps secrets. Add Sentry for exception tracing and Datadog for logs, metrics, queue depth, worker failures, latency, duplicates, and status inconsistencies.
- Set Azure cost alerts at $25, $50, $75, and $90; use low worker concurrency, scale-to-zero, short log retention, and delete the resource group after the exercise.

## Test plan

- Unit-test validation, mocked extraction, statuses, retry rules, idempotency, review state transitions, and MongoDB audit-event emission.
- Integration-test ZIP upload through batch completion, including 1,000 documents, size boundaries, malformed ZIPs, duplicate task delivery, provider timeout, retry exhaustion, and concurrent reviewer actions.
- Run the same contract test suite against Django, FastAPI, and Flask.
- Perform deployment smoke tests for each subdomain, health endpoint, upload-to-review workflow, Sentry error capture, Datadog telemetry, alert thresholds, and TLS.

## Assumptions

- Version one uses Keycloak OIDC bearer tokens with `submitter`, `reviewer`, and `administrator` roles. Review records store both the verified subject and a supplied display name; production Keycloak hosting is still a deployment task.
- No frontend is required; Swagger/OpenAPI plus API clients are the review interface.
- MongoDB is an existing managed account funded separately.
- Azure region, exact domain names, subscription, and observability credentials are supplied during execution.
