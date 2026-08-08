#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://127.0.0.1:8081}"
REALM="contract-processing"
CLIENT_ID="contract-processing-api"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

token_for() {
  local username="$1"
  local password="$2"
  curl --fail --silent --show-error -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode "client_id=$CLIENT_ID" \
    --data-urlencode 'grant_type=password' \
    --data-urlencode "username=$username" \
    --data-urlencode "password=$password" \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])'
}

python3 - "$TEMP_DIR/contracts.zip" <<'PY'
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1], "w") as archive:
    archive.writestr("sample-agreement.txt", "Sample contract for local smoke testing.")
PY

echo "Checking API health..."
curl --fail --silent --show-error "$API_URL/api/health/" >/dev/null

echo "Getting Keycloak submitter token..."
SUBMITTER_TOKEN="$(token_for submitter 'Submit123!')"

echo "Uploading one contract batch..."
UPLOAD_RESPONSE="$(curl --fail --silent --show-error -X POST "$API_URL/api/batches/" \
  -H "Authorization: Bearer $SUBMITTER_TOKEN" \
  -F "zip_file=@$TEMP_DIR/contracts.zip" \
  -F 'variables=["effective_date", "monthly_rent"]')"
BATCH_ID="$(printf '%s' "$UPLOAD_RESPONSE" | python3 -c 'import json, sys; print(json.load(sys.stdin)["id"])')"

echo "Waiting for Celery extraction (batch $BATCH_ID)..."
for _ in $(seq 1 20); do
  BATCH_RESPONSE="$(curl --fail --silent --show-error "$API_URL/api/batches/$BATCH_ID/" -H "Authorization: Bearer $SUBMITTER_TOKEN")"
  BATCH_STATUS="$(printf '%s' "$BATCH_RESPONSE" | python3 -c 'import json, sys; print(json.load(sys.stdin)["status"])')"
  if [ "$BATCH_STATUS" = "completed" ]; then
    break
  fi
  sleep 1
done

if [ "${BATCH_STATUS:-}" != "completed" ]; then
  echo "Batch did not complete. Last payload: $BATCH_RESPONSE" >&2
  exit 1
fi

FINDING_ID="$(printf '%s' "$BATCH_RESPONSE" | python3 -c 'import json, sys; print(json.load(sys.stdin)["documents"][0]["findings"][0]["id"])')"
echo "Getting Keycloak reviewer token..."
REVIEWER_TOKEN="$(token_for reviewer 'Review123!')"

echo "Accepting finding $FINDING_ID as reviewer..."
REVIEW_RESPONSE="$(curl --fail --silent --show-error -X PATCH "$API_URL/api/findings/$FINDING_ID/review/" \
  -H "Authorization: Bearer $REVIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"decision":"accepted","reviewer_name":"Local Reviewer"}')"
REVIEW_STATUS="$(printf '%s' "$REVIEW_RESPONSE" | python3 -c 'import json, sys; print(json.load(sys.stdin)["review_status"])')"

if [ "$REVIEW_STATUS" != "accepted" ]; then
  echo "Finding review did not persist: $REVIEW_RESPONSE" >&2
  exit 1
fi

echo "PASS: authenticated upload, Celery extraction, batch tracking, and reviewer acceptance succeeded."
echo "Batch ID: $BATCH_ID"
