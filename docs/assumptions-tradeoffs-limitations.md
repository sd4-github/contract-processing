# Assumptions, trade-offs, and limitations

## Assumptions

- The API receives a multipart ZIP and a JSON-encoded non-empty list of unique
  variable names. There is no frontend-specific request format.
- Extraction is a deterministic mock. The same bytes and variable list produce
  the same values, which makes retries and contract tests reproducible.
- PostgreSQL is the production source of truth. SQLite and local `media/` are
  only zero-setup development/test defaults.
- Redis/Celery provides at-least-once delivery. Workers must therefore tolerate
  duplicates, crashes, and retries.
- Keycloak supplies OIDC access tokens and the three application roles. The
  checked-in realm and user passwords are development fixtures only.
- MongoDB is available for operational audit events but must not be required for
  a successful contract transaction.
- Azure resources, a DNS zone, a domain, Sentry credentials, and Datadog
  credentials will be supplied before deployment work begins.

## Deliberate trade-offs

| Decision | Benefit | Cost or alternative |
|---|---|---|
| PostgreSQL as the state authority | Transactions, constraints, row locks, and queryable status | Requires migrations, backups, and connection management |
| Redis/Celery instead of inline extraction | Fast upload response and independent worker scaling | At-least-once delivery and broker operations must be handled |
| Deterministic mock provider | Reproducible tests and safe reprocessing | Does not model real OCR/LLM quality or provider semantics |
| MongoDB audit sink | Append-only event history without coupling it to relational writes | Cross-store consistency is eventual; event delivery can be lost during outages |
| Local/Azure Blob storage abstraction | Same application code for development and deployment | Blob lifecycle, credentials, network policy, and container provisioning are operational concerns |
| Framework-equivalent implementations | Useful comparison and migration practice | Deliberate duplication increases maintenance and contract-drift risk |
| Row locks for reviews | Prevents concurrent reviewers from overwriting a read-modify-write operation | Lock contention must be observed; SQLite cannot faithfully reproduce it |
| Late Celery acknowledgements and bounded retries | Crashes do not silently discard work; transient I/O is retried | A task may be visible more than once and needs idempotent writes |

## Known limitations

- Live Keycloak, Redis, PostgreSQL, Celery, MongoDB, Azure Blob, Sentry, and
  Datadog verification has not been completed in this workspace because Docker
  access is denied and no Azure credentials are in scope.
- The API checks every member’s uncompressed size and the file-count limit, but
  does not impose a total uncompressed archive budget or a compression-ratio
  limit. A future hardening pass should add those limits to reduce archive-bomb
  risk.
- Upload bytes are written before the relational commit. A failed transaction
  can leave an orphaned local file or Blob; a cleanup job and object lifecycle
  policy are required in production.
- Mongo audit writes are best effort. They are not an immutable compliance log,
  and the current implementation does not use an outbox table.
- Retryable processing currently exposes a failed document while a retry is
  pending, then recomputes the state on the next attempt. A production UI may
  want a distinct `retrying` state.
- The development Keycloak realm uses password grant fixtures and simple local
  credentials. Production should use hardened clients, secret rotation,
  backup/restore, and an agreed login flow.
- Flask does not generate an interactive schema. Clients should use the shared
  checked-in OpenAPI document; the contract suite is the drift detector.
- The extraction values are demonstrations only. They must be replaced by a
  provider interface with explicit timeouts, quotas, redaction policy, and
  human-review rules before handling real contracts.

## Out of scope for this workspace

The frontend, production identity hosting, Azure resource provisioning, DNS/TLS
changes, budget creation, image publication, and destructive teardown require
external authority and credentials. They are described in
[deployment-plan.md](deployment-plan.md) but are not implied by local code
changes.
