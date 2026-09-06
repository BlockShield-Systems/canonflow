#!/usr/bin/env bash
# Layer-by-layer smoke test. Read-only: no model calls, no renders.
cf_base="${1:-http://127.0.0.1:8081}"
cf_mcp="${CF_MCP_ENDPOINT:-http://127.0.0.1:8000/mcp}"
cf_ok=0; cf_bad=0

cf_check() {  # name expected actual
  if [ "$2" = "$3" ]; then printf '  PASS  %-34s %s\n' "$1" "$3"; cf_ok=$((cf_ok+1))
  else printf '  FAIL  %-34s got=%s want=%s\n' "$1" "$3" "$2"; cf_bad=$((cf_bad+1)); fi
}

echo "== 1. web layer ($cf_base)"
cf_check "console /review" 200 \
  "$(curl -s -o /dev/null -w '%{http_code}' "$cf_base/review/")"
cf_check "adk /list-apps" 200 \
  "$(curl -s -o /dev/null -w '%{http_code}' "$cf_base/list-apps")"
cf_check "openapi /docs" 200 \
  "$(curl -s -o /dev/null -w '%{http_code}' "$cf_base/docs")"

echo "== 2. clickhouse mcp ($cf_mcp)"
cf_check "mcp initialize" 200 \
  "$(curl -s -o /dev/null -w '%{http_code}' \
     -H "Authorization: Bearer $CLICKHOUSE_MCP_AUTH_TOKEN" \
     -H 'Content-Type: application/json' \
     -H 'Accept: application/json, text/event-stream' \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}' \
     "$cf_mcp")"

echo "== 3. vertex auth"
cf_check "CF_PROJECT set" yes "$([ -n "$CF_PROJECT" ] && echo yes || echo no)"
cf_check "ADC token" yes \
  "$(gcloud auth application-default print-access-token >/dev/null 2>&1 \
     && echo yes || echo no)"

echo "== 4. run artifacts"
cd "$(dirname "$0")/.." || exit 1
uv run python - <<'CF_PY_EOF'
from canonflow_agent.ui import data
idx = data.scan()
bad_v = [k for k, r in idx.items() if r["verdict"] != "PASS"]
bad_s = [k for k, r in idx.items() if not r["ctx_state_ok"]]
no_p = [k for k, r in idx.items() if not r["prompts"]]
print(f"  {'PASS' if len(idx)==44 else 'FAIL'}  beats indexed                      {len(idx)}/44")
print(f"  {'PASS' if not bad_v else 'FAIL'}  canon verdict PASS                 {bad_v or 'all'}")
print(f"  {'PASS' if not bad_s else 'FAIL'}  ctx_state (clickhouse) present     {bad_s or 'all'}")
print(f"  {'PASS' if not no_p else 'FAIL'}  prompts present                    {no_p or 'all'}")
CF_PY_EOF

echo
echo "curl checks: $cf_ok pass, $cf_bad fail"
