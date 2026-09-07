#!/usr/bin/env bash
# Verifies /api/sidekick/control bearer auth without changing any hardware state.
# Uses a bogus target so an authenticated request stops at validation (HTTP 400).
set -u
BASE="http://127.0.0.1:8080"
KEY="$(cat /home/bcaddy/uconsole-k7bat/.apikey)"
PAYLOAD='{"target":"NOPE","command":"power","value":"on"}'

code() { curl -s -o /dev/null -m 10 -w '%{http_code}' "$@"; }

echo "no auth        -> $(code -X POST "$BASE/api/sidekick/control" -H 'Content-Type: application/json' -d "$PAYLOAD")  (expect 401)"
echo "wrong token    -> $(code -X POST "$BASE/api/sidekick/control" -H 'Authorization: Bearer nope' -H 'Content-Type: application/json' -d "$PAYLOAD")  (expect 401)"
echo "correct token  -> $(code -X POST "$BASE/api/sidekick/control" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -d "$PAYLOAD")  (expect 400 = auth passed, target rejected)"

echo
echo "GET /api/sidekick (no auth needed):"
curl -s -m 10 "$BASE/api/sidekick"; echo
echo
echo "orphan gpspipe processes: $(pgrep -c gpspipe 2>/dev/null || echo 0)"
