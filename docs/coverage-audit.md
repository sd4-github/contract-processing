# Plan and tool coverage audit

This matrix records the current state of every material tool and deliverable in
`PLAN.md` and `CHECKLIST.md`. “Configured” means source/configuration exists;
it does not claim a live external service was verified.

| Area/tool | Django | FastAPI | Flask | Status / required next step |
|---|---|---|---|---|
| REST API: batches, documents, findings, review | implemented | implemented | implemented | `docs/openapi.json` and the shared runner cover the common HTTP contract. |
| PostgreSQL source of truth | configured, migration exists | configured, Alembic migration exists | configured, Alembic migration exists | Migrations apply in a dedicated Compose service; live PostgreSQL verification remains blocked by Docker access. |
| Redis + Celery | configured | configured | configured | Retry scheduling/exhaustion and time limits are unit-tested; verify delivery and concurrency with live Compose. |
| MongoDB audit events | implemented | implemented | implemented | Batch/document queued, attempt, retry, completion, failure, and review events are covered in code; live Mongo verification remains. |
| Keycloak OIDC and roles | implemented | implemented | implemented | Run real-token integration tests; configure a production realm. |
| ZIP safety and 1,000/15 MB limits | implemented | implemented | implemented | Malformed ZIP, exact boundary, and safety cases are covered by local contract tests. |
| Idempotency/status aggregation | implemented | implemented | implemented | Duplicate delivery and partial failure are covered; PostgreSQL-only concurrent review tests are ready. |
| OpenAPI/interactive docs | schema, Swagger, ReDoc | automatic OpenAPI/Swagger | no generated schema | `docs/openapi.json` is the checked-in shared contract; the shared runner exercises all three APIs. |
| Framework tests | 8 tests passed | 8 tests passed | 8 tests passed | Concurrent-review tests run only with PostgreSQL; current SQLite runs verify all other local paths. |
| Docker Compose | configuration validated | configuration validated | configuration validated | Docker daemon access blocks live startup/smoke tests. |
| Azure Blob Storage | configuration support | local/Azure Blob abstraction and config | local/Azure Blob abstraction and config | Azure account/container provisioning and managed-identity smoke test remain deployment work. |
| Sentry and Datadog | configuration support | opt-in SDK/configuration | opt-in SDK/configuration | DSN, service, environment, release, and trace settings are wired; live telemetry/alerts remain deployment work. |
| Azure Container Apps, ACR, Key Vault, KEDA, DNS/TLS | deployment plan only | deployment plan only | deployment plan only | Requires Azure subscription, domain/DNS, credentials, and explicit deployment authority. |
| Shared docs | architecture, assumptions/limitations, framework comparison, incident report, local guides, and deployment plan | same shared docs plus local guide | same shared docs plus local guide | Complete for local delivery; deployment runbooks still require live resource details. |

## Mandatory delivery order

1. Restore Docker daemon access and run the three live workflow guides.
2. Complete the remaining design/case-study documents.
3. Execute the Azure plan in [deployment-plan.md](deployment-plan.md), beginning with Django.

## Known implementation differences to resolve before deployment

- FastAPI and Flask use reviewed Alembic migrations in a dedicated Compose
  service; tests still use `create_all()` only to create isolated SQLite fixtures.
- The plan's original “random normal-run extraction” rule has been made
  deterministic across all frameworks. This preserves retry/idempotency safety
  and matches the existing Django behavior.
- The local Keycloak realm is deliberately shared as a development fixture. A
  production realm, secret handling, rotation, backups, and redirect URIs are
  not yet configured.
