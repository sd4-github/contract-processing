# Django vs. FastAPI vs. Flask

All three implementations expose the same five operations and use the same
state model, task semantics, Keycloak roles, and checked-in OpenAPI contract.
The comparison is about framework shape rather than product behavior.

| Concern | Django + DRF | FastAPI | Flask |
|---|---|---|---|
| Primary strength here | Batteries-included ORM, migrations, admin ecosystem, and mature request lifecycle | Typed request declarations, generated interactive schema, and clear dependency injection | Small core and explicit composition; easy to understand the minimal request path |
| Persistence | Django ORM and built-in migrations | SQLAlchemy 2 with Alembic | SQLAlchemy 2 with Alembic |
| Validation/schema | DRF serializers plus drf-spectacular | Pydantic and generated OpenAPI | Hand-written validation and shared external OpenAPI |
| Dependency injection | Permissions/authentication classes and Django request context | `Depends()` makes auth and sessions explicit in signatures | Decorators and Flask request globals |
| Async fit | Synchronous views with Celery for background work | ASGI-capable, but this implementation deliberately keeps synchronous SQLAlchemy work in sync endpoints | WSGI request handling with Celery for background work |
| Operational maturity | Strong conventions and a broad ecosystem; more framework machinery | Excellent API ergonomics; deployment must still handle migrations and workers | Very flexible; conventions and boundaries must be supplied by the team |
| Local documentation | Swagger UI/ReDoc through drf-spectacular | `/docs` and `/openapi.json` automatically | Shared `docs/openapi.json`; no generated UI in the app |
| Best use in this exercise | Reference implementation for relational and operational patterns | Reference implementation for typed API design | Comparison target for a deliberately minimal service |

## Decision for this system

FastAPI is the reference for the external API shape because typed multipart
declarations and generated schema make drift visible early. Django remains the
reference for migration and convention-heavy production patterns. Flask is a
useful minimal comparison, but it needs stronger project conventions—shared
tests, explicit migrations, and a checked-in contract—to avoid silent drift.

The deployment plan intentionally keeps all three available for learning. In a
single production product, operating three equivalent stacks would usually be an
unnecessary cost; one framework should be selected after team, ecosystem,
latency, and support requirements are known.

## Shared contract as the boundary

The external contract, not internal model names, is the compatibility boundary.
`contract_tests/suite.py` runs the same health, upload, status, document, review,
malformed-ZIP, Windows-path, and size-boundary assertions against each in-process
client. The PostgreSQL-only concurrency checks verify the locking behavior that
SQLite cannot model.
