# Contract-processing architecture

This document describes the current reference design for the three equivalent
API implementations. Development can run with SQLite and local files; the
deployed design uses PostgreSQL, Redis, MongoDB, Keycloak, and Azure Blob
Storage.

## Component boundaries

| Component | Responsibility | Durability/authority |
|---|---|---|
| Django, FastAPI, or Flask API | Authenticate requests, validate ZIP metadata, persist batches/documents, expose status and review endpoints | Stateless; PostgreSQL is authoritative |
| PostgreSQL | Batches, document metadata and states, findings, reviewer decisions, aggregate status | Transactional source of truth |
| Redis + Celery | Queue one extraction task per document, late acknowledgements, bounded retries, time limits | Delivery mechanism; at-least-once |
| Extraction service | Deterministic mocked variable extraction | Recomputable from stored bytes and variables |
| MongoDB | Append-only processing/audit events | Operational telemetry; best effort |
| Local storage or Azure Blob | Original document bytes | Shared worker-readable object storage in production |
| Keycloak | OIDC bearer tokens and `submitter`, `reviewer`, `administrator` roles | Identity authority |
| Sentry and Datadog | Error traces, logs, traces, and operational signals | Observability only |

The three APIs share the HTTP contract in [openapi.json](openapi.json). Their
framework-specific models are intentionally separate so each implementation can
be studied and deployed independently.

## Upload-to-review flow

```text
client -> API -> validate ZIP and variables
              -> write document bytes and PostgreSQL rows
              -> commit transaction
              -> publish Celery task + audit queued event
worker -> claim document -> mark processing
        -> read object bytes -> extract values
        -> upsert findings -> mark document terminal -> recompute batch
reviewer -> lock finding row -> persist decision and verified subject
```

The API never extracts archive members as paths. It reads each validated member
directly, stores it under a generated storage name, and queues work only after
the database transaction commits. Django uses `transaction.on_commit`; the
SQLAlchemy applications commit before publishing in the request handler.

## Data and state model

`Batch` owns one or more `ContractDocument` records. Each document has zero or
more uniquely keyed findings (`document_id`, `variable_name`). A finding’s
extraction status is separate from its review status, so a completed extraction
can remain pending human review.

Batch status is derived from all document states:

- `processing` if any document is processing;
- `pending` if no document is processing but at least one is pending;
- `completed` or `failed` when all documents have that terminal state;
- `partial_failed` for a mixture of completed and failed documents.

This avoids a fragile counter that could become incorrect after worker crashes or
duplicate messages. Review writes use a row lock in PostgreSQL, and the unique
finding constraint protects against duplicate delivery.

## Reliability and failure handling

Celery uses late acknowledgements, a prefetch multiplier of one, soft and hard
time limits, and retries for transient `OSError` failures. Each attempt,
scheduled retry, exhausted retry, completion, and failure emits an audit event.
Non-transient exceptions become visible failed documents instead of being
retried indefinitely. A terminal completed document is an idempotency guard.

MongoDB audit delivery is deliberately best effort: a Mongo outage is logged and
does not roll back a committed contract transaction. PostgreSQL status and
findings remain authoritative.

FastAPI and Flask apply `alembic upgrade head` through a dedicated Compose
migration service. Test fixtures may use `create_all()` for isolated SQLite
databases, but application startup does not mutate production schemas.

## Security boundaries

- Keycloak bearer tokens are validated against issuer, audience, signature, and
  realm/client roles when `AUTH_ENABLED=true`.
- Submission requires `submitter` or `administrator`; review requires
  `reviewer` or `administrator`; reads require any application role.
- ZIP paths reject absolute paths, parent traversal, Windows separators,
  unsupported extensions, and members over 15 MiB. A batch is capped at 1,000
  files.
- Secrets, production Keycloak credentials, Blob credentials, Sentry DSNs, and
  Datadog keys belong in Key Vault/Container App secrets, not source control.

## Deployment shape

The intended Azure deployment has one public API and one internal worker for
each framework. ACR supplies immutable images; Container Apps runs the APIs and
workers; KEDA scales workers from Redis depth; PostgreSQL, Redis, Blob Storage,
Key Vault, and Log Analytics are managed services. The deployment plan remains
pending because it requires an Azure subscription, domain, and operator
credentials.
