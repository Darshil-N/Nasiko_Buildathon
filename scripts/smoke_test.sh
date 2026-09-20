#!/usr/bin/env bash
# End-to-end smoke test against a running backend (plan step 4.9.3, checked at 8.3.1).
#
# Exercises the golden path for real: categories, create an analysis, poll it to completion,
# recommendations (json and geojson), zone detail, cells, compare, what-if and chat. Measures
# wall-clock time for the create-to-done step against the 30-second target (step 8.3.2).
#
# Usage:
#   BACKEND_API_KEY=... ./scripts/smoke_test.sh [base_url]
#
# Requires: curl, python (already a project dependency, used only to read fields out of JSON
# responses so this script needs no extra tools like jq).
set -euo pipefail

BASE_URL="${1:-http://localhost:8000/v1}"
API_KEY="${BACKEND_API_KEY:-}"
if [ -z "$API_KEY" ]; then
  echo "Set BACKEND_API_KEY in the environment before running this script." >&2
  exit 1
fi
PY="${PYTHON:-python}"
command -v "$PY" >/dev/null 2>&1 || PY=".venv/Scripts/python.exe"

HEADERS=(-H "X-API-Key: $API_KEY" -H "X-User-Id: smoke-test" -H "Content-Type: application/json")
FAILED=0

jget() {  # jget <json> <python-expression-using-d>
    "$PY" -c "import json,sys; d=json.loads(sys.argv[1]); print($2)" "$1"
}

check() {  # check <description> <expected-status> <actual-status>
    if [ "$3" = "$2" ]; then
        echo "  ok   $1 (HTTP $3)"
    else
        echo "  FAIL $1 (expected HTTP $2, got $3)"
        FAILED=1
    fi
}

echo "SiteScout smoke test against $BASE_URL"

# --- categories and cities ---------------------------------------------------------------------
status=$(curl -s -o /tmp/cats.json -w "%{http_code}" "$BASE_URL/categories" "${HEADERS[@]}")
check "GET /categories" 200 "$status"

status=$(curl -s -o /tmp/cities.json -w "%{http_code}" "$BASE_URL/cities" "${HEADERS[@]}")
check "GET /cities" 200 "$status"

# --- create and poll ----------------------------------------------------------------------------
started=$(date +%s)
create_body='{"city":"bengaluru","category":"cafe","tier":"mid","answers":{},"constraints":{"top_n":5}}'
status=$(curl -s -o /tmp/create.json -w "%{http_code}" -X POST "$BASE_URL/analyses" "${HEADERS[@]}" -d "$create_body")
check "POST /analyses" 202 "$status"
analysis_id=$(jget "$(cat /tmp/create.json)" "d['analysis_id']")
echo "  analysis: $analysis_id"

result_status="queued"
for _ in $(seq 1 30); do
    curl -s -o /tmp/poll.json "$BASE_URL/analyses/$analysis_id" "${HEADERS[@]}"
    result_status=$(jget "$(cat /tmp/poll.json)" "d['status']")
    [ "$result_status" = "done" ] || [ "$result_status" = "failed" ] && break
    sleep 1
done
elapsed=$(( $(date +%s) - started ))
if [ "$result_status" = "done" ]; then
    echo "  ok   analysis completed in ${elapsed}s"
    [ "$elapsed" -le 30 ] && echo "  ok   under the 30s target (8.3.2)" || echo "  WARN over the 30s target (8.3.2): ${elapsed}s"
else
    echo "  FAIL analysis did not complete (status: $result_status)"
    FAILED=1
fi

# --- recommendations, zone detail, cells --------------------------------------------------------
status=$(curl -s -o /tmp/recs.json -w "%{http_code}" "$BASE_URL/analyses/$analysis_id/recommendations" "${HEADERS[@]}")
check "GET /analyses/{id}/recommendations" 200 "$status"

status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/analyses/$analysis_id/recommendations?format=geojson" "${HEADERS[@]}")
check "GET /analyses/{id}/recommendations?format=geojson" 200 "$status"

status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/analyses/$analysis_id/zones/1" "${HEADERS[@]}")
check "GET /analyses/{id}/zones/1" 200 "$status"

status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/analyses/$analysis_id/cells" "${HEADERS[@]}")
check "GET /analyses/{id}/cells" 200 "$status"

# --- compare, what-if, chat -----------------------------------------------------------------------
zone_ids=$(jget "$(cat /tmp/recs.json)" "','.join(z['h3_index'] for z in d['recommendations'][:2])")
compare_body="{\"zone_h3_indices\": [\"${zone_ids//,/\", \"}\"]}"
status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/analyses/$analysis_id/compare" "${HEADERS[@]}" -d "$compare_body")
check "POST /analyses/{id}/compare" 200 "$status"

status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/analyses/$analysis_id/what-if" "${HEADERS[@]}" -d '{"tier": "premium"}')
check "POST /analyses/{id}/what-if" 200 "$status"

status=$(curl -s -o /tmp/chat.json -w "%{http_code}" -X POST "$BASE_URL/analyses/$analysis_id/chat" "${HEADERS[@]}" -d '{"question": "Why does the top zone rank first?"}')
check "POST /analyses/{id}/chat" 200 "$status"
grounded=$(jget "$(cat /tmp/chat.json)" "d['grounded']")
echo "  chat grounded: $grounded (false is a normal, honest outcome with the small local model)"

# --- history --------------------------------------------------------------------------------------
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/analyses" "${HEADERS[@]}")
check "GET /analyses" 200 "$status"

rm -f /tmp/cats.json /tmp/cities.json /tmp/create.json /tmp/poll.json /tmp/recs.json /tmp/chat.json

if [ "$FAILED" -eq 0 ]; then
    echo "smoke test passed"
    exit 0
else
    echo "smoke test FAILED"
    exit 1
fi
