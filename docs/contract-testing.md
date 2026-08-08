# Contract and failure-path testing

`docs/openapi.json` is the checked-in HTTP contract shared by the Django, FastAPI,
and Flask implementations. The framework-specific `test_contract.py` files only
adapt each in-process client; their assertions are shared by
`contract_tests/suite.py`.

Run the suites from their isolated environments:

```bash
cd django_drf && .venv/bin/python manage.py test
cd ../fastapi && .venv/bin/pytest
cd ../flask && .venv/bin/pytest
```

The local suites cover the public workflow, malformed ZIPs, the exact 15 MiB
member boundary, duplicate delivery, partial batch failure, retry scheduling and
exhaustion, task time limits, and local/Azure storage adapter behavior. The
concurrent-review tests are deliberately skipped on SQLite and run when
`POSTGRES_HOST`/PostgreSQL is configured, because SQLite cannot provide the row
locking semantics used in production.
