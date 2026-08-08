# Live FastAPI workflow validation

This validates the FastAPI implementation against its own local stack. It uses
the same imported development Keycloak realm as Django, but exposes FastAPI on
port 8002 and Keycloak on port 8082.

For the production sequence after this local validation passes, follow the
[shared deployment plan](deployment-plan.md).

## Start the stack

First make sure Docker access works. If `docker info` reports a permission
error for `/var/run/docker.sock`, follow the remedy in
[the Django live-workflow guide](live-django-workflow.md#prerequisites).

```bash
cd fastapi
uv sync
uv run pytest
cp .env.example .env
docker compose up --build -d
docker compose ps
curl --fail http://localhost:8002/api/health/
```

`uv sync` creates FastAPI's isolated `.venv`; it must be run before the local
test command. Open `http://localhost:8002/docs` for FastAPI's Swagger UI.

## Authenticated upload and review

```bash
SUBMITTER_TOKEN=$(curl -fsS -X POST \
  http://localhost:8082/realms/contract-processing/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=contract-processing-api&grant_type=password&username=submitter&password=Submit123!' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

REVIEWER_TOKEN=$(curl -fsS -X POST \
  http://localhost:8082/realms/contract-processing/protocol/openid-connect/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=contract-processing-api&grant_type=password&username=reviewer&password=Review123!' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

python3 - <<'PY'
import zipfile
with zipfile.ZipFile('/tmp/fastapi-contracts.zip', 'w') as archive:
    archive.writestr('agreement.txt', 'Sample contract for live validation.')
PY

UPLOAD=$(curl -fsS -X POST http://localhost:8002/api/batches/ \
  -H "Authorization: Bearer $SUBMITTER_TOKEN" \
  -F 'zip_file=@/tmp/fastapi-contracts.zip' \
  -F 'variables=["effective_date", "monthly_rent"]')
BATCH_ID=$(printf '%s' "$UPLOAD" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
```

Poll `GET /api/batches/$BATCH_ID/` with the submitter token until its `status`
is `completed`. Then PATCH a returned finding with the reviewer token:

```bash
curl -fsS http://localhost:8002/api/batches/$BATCH_ID/ \
  -H "Authorization: Bearer $SUBMITTER_TOKEN"

curl -fsS -X PATCH http://localhost:8002/api/findings/FINDING_ID/review/ \
  -H "Authorization: Bearer $REVIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"decision":"accepted","reviewer_name":"Local Reviewer"}'
```

Replace `FINDING_ID` with an ID in the batch response.

## Verify infrastructure and clean up

```bash
docker compose logs --tail=150 worker
docker compose exec postgres psql -U contracts -d contracts -c \
  'select id, status, completed_at from batches;'
docker compose exec postgres psql -U contracts -d contracts -c \
  'select original_filename, status, processed_at from documents;'
docker compose exec redis redis-cli ping
docker compose exec mongodb mongosh --quiet contract_processing --eval \
  'db.events.find({}, {event_type:1, occurred_at:1, _id:0}).sort({occurred_at:1}).toArray()'
docker compose down
```

MongoDB should contain batch, processing, completion, and review events. Use
`docker compose down -v` only when intentionally deleting local data.
