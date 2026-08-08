# Live Flask workflow validation

This validates the Flask implementation against its separate local stack.
Flask is served on port 8003; its Keycloak instance is exposed on 8083.

For the production sequence after this local validation passes, follow the
[shared deployment plan](deployment-plan.md).

## Start the stack

If Docker reports a permission error for `/var/run/docker.sock`, resolve that
first using [the Django guide's prerequisite steps](live-django-workflow.md#prerequisites).

```bash
cd flask
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
cp .env.example .env
docker compose up --build -d
docker compose ps
curl --fail http://localhost:8003/api/health/
```

## Authenticated upload and review

Get the local `submitter` and `reviewer` Keycloak tokens. The supplied users
are development-only credentials from the imported realm.

```bash
token_for() {
  curl -fsS -X POST http://localhost:8083/realms/contract-processing/protocol/openid-connect/token \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "client_id=contract-processing-api&grant_type=password&username=$1&password=$2" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
}
SUBMITTER_TOKEN=$(token_for submitter 'Submit123!')
REVIEWER_TOKEN=$(token_for reviewer 'Review123!')

python3 - <<'PY'
import zipfile
with zipfile.ZipFile('/tmp/flask-contracts.zip', 'w') as archive:
    archive.writestr('agreement.txt', 'Sample contract for live validation.')
PY

UPLOAD=$(curl -fsS -X POST http://localhost:8003/api/batches/ \
  -H "Authorization: Bearer $SUBMITTER_TOKEN" \
  -F 'zip_file=@/tmp/flask-contracts.zip' \
  -F 'variables=["effective_date", "monthly_rent"]')
BATCH_ID=$(printf '%s' "$UPLOAD" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
```

Poll the batch endpoint until `status` is `completed`, copy a returned finding
ID, then make the review request:

```bash
curl -fsS http://localhost:8003/api/batches/$BATCH_ID/ \
  -H "Authorization: Bearer $SUBMITTER_TOKEN"

curl -fsS -X PATCH http://localhost:8003/api/findings/FINDING_ID/review/ \
  -H "Authorization: Bearer $REVIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"decision":"accepted","reviewer_name":"Local Reviewer"}'
```

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

Successful validation gives a completed PostgreSQL batch/document, a reviewed
finding, `PONG` from Redis, and MongoDB audit lifecycle events. Use
`docker compose down -v` only when deleting test data is intended.
