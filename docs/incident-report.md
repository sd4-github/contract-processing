# Production-incident cause and remediation report

## Status of this report

This is a representative incident case study derived from the failure modes the
system is designed to prevent. No live Azure or Docker production incident was
observed in this workspace; the live validation phase is blocked by Docker
daemon access.

## Simulated incident summary

After a worker restart during a high-volume upload, a batch contained documents
that were visible in the API but had no completed findings. A redelivered task
also attempted to write the same finding twice. Operators initially saw only a
generic batch status and could not correlate the missing work with a queue
attempt because audit events were incomplete.

### Customer and operational impact

- Some batches remained pending or failed until an operator replayed work.
- Reviewers could not trust that a completed-looking batch contained every
  finding.
- No contract bytes were intentionally exposed or deleted; the primary impact
  was processing delay and loss of operational confidence.
- The incident would be high severity for an automated downstream consumer, but
  human review provides a containment point before acceptance.

## Cause and remediation table

| Cause | Failure mechanism | Remediation | Verification |
|---|---|---|---|
| Task published before upload transaction committed | A worker could consume an ID whose rows later rolled back | Commit before publish in FastAPI/Flask; `transaction.on_commit` in Django | Upload tests assert queue publication after durable rows exist; live smoke test remains |
| Non-idempotent finding writes | At-least-once delivery could create duplicate variable findings | Unique `(document_id, variable_name)` constraint plus update/upsert and completed-state guard | Duplicate-delivery tests pass in all three implementations |
| Batch status maintained by counters | A crash or duplicate could leave aggregate status incorrect | Recompute status from durable document rows; lock aggregate in Django | Partial-failure and duplicate tests pass |
| Retry policy was opaque | Operators could not distinguish an attempt from a terminal failure | Emit attempt, retry-scheduled, retry-exhausted, start, completion, and failure events | Task tests assert scheduled and exhausted event payloads; live Mongo check remains |
| Audit sink coupled to business transaction | Mongo latency/outage could block or roll back contract work | Treat Mongo as best-effort telemetry and log delivery failures | Audit module catches sink errors; PostgreSQL remains authoritative |
| Concurrent review writes | Two reviewers could overwrite a decision without serialization | Lock the finding row with `select_for_update` / `with_for_update` | PostgreSQL-only concurrent-review tests are ready; SQLite skips the check |
| No deployment schema gate | A new worker/API could run against an old schema | Dedicated Alembic migration service before FastAPI/Flask API and worker | Fresh SQLite migrations reach `0001_initial (head)`; live Compose check remains |

## Response runbook

1. Stop promotion of the affected API/worker revision and preserve queue and
   audit logs.
2. Query PostgreSQL for batches with pending/failed documents and identify the
   document IDs, not just the batch counter.
3. Inspect Redis task state and Mongo attempt/retry events. Do not infer a
   successful extraction from a queue acknowledgement alone.
4. Replay only non-completed document IDs. The terminal-state guard and unique
   finding key make a safe replay possible.
5. Confirm every replayed batch from PostgreSQL, then allow reviewers to act.
6. Export the event timeline, deployment revision, database migration revision,
   and queue metrics for the post-incident review.

## Preventive controls still required before production

- Run the live authenticated workflow against PostgreSQL, Redis/Celery, and
  MongoDB for each API.
- Add an outbox or durable audit-delivery queue if audit completeness becomes a
  compliance requirement.
- Add total archive/uncompressed-byte limits and a cleanup job for orphaned
  local/Blob objects.
- Alert on retry exhaustion, failed/partial batches, queue age, status
  inconsistencies, database capacity, and audit-sink failures.
