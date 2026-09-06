#!/usr/bin/env bash
# Regenerates docs/STATE.md from live sources. Read-only, no deploys.
set -u
cf_proj=canonflow-agentic-cinema
cf_region=europe-west4
cd "$(dirname "$0")/.." || exit 1
mkdir -p docs
out=docs/STATE.md

{
echo "# CANONFLOW — STATE"
echo
echo "Generated: \`$(date -u +%Y-%m-%dT%H:%M:%SZ)\` by \`scripts/state.sh\`."
echo "Every number below comes from a live query, not from memory."
echo
echo '## Repo'
echo '```'
git rev-parse --abbrev-ref HEAD 2>/dev/null | sed 's/^/branch: /'
git log -1 --format='head:   %h %ad %s' --date=short 2>/dev/null
git remote get-url origin 2>/dev/null | sed 's/^/origin: /'
echo "dirty:  $(git status --porcelain 2>/dev/null | wc -l) files"
echo "license: $(ls LICENSE 2>/dev/null || echo MISSING)"
echo '```'
echo
echo '## Cloud Run'
echo '```'
gcloud run services list --project "$cf_proj" \
  --format="table[no-heading](metadata.name,status.url,status.latestReadyRevisionName)"
echo '```'
echo
echo '### canonflow-agent (containers / image digests)'
echo '```'
gcloud run services describe canonflow-agent --region "$cf_region" --project "$cf_proj" \
  --format="value[separator='
'](spec.template.spec.containers[].name,spec.template.spec.containers[].image)" 2>/dev/null
echo "--"
gcloud run services describe canonflow-agent --region "$cf_region" --project "$cf_proj" \
  --format="value(spec.template.spec.serviceAccountName)" | sed 's/^/sa:       /'
gcloud run services describe canonflow-agent --region "$cf_region" --project "$cf_proj" \
  --format="value(metadata.annotations['run.googleapis.com/ingress'])" | sed 's/^/ingress:  /'
gcloud run services describe canonflow-agent --region "$cf_region" --project "$cf_proj" \
  --format="value(spec.template.metadata.annotations['run.googleapis.com/network-interfaces'])" | sed 's/^/vpc:      /'
gcloud run services describe canonflow-agent --region "$cf_region" --project "$cf_proj" \
  --format="value(spec.template.spec.containers[0].env[].name)" | tr ';' ' ' | sed 's/^/env keys: /'
gcloud run services get-iam-policy canonflow-agent --region "$cf_region" --project "$cf_proj" \
  --format="value(bindings.members)" | sed 's/^/invoker:  /'
echo '```'
echo
echo '## Network'
echo '```'
gcloud compute networks list --project "$cf_proj" --format="table[no-heading](name,subnet_mode)"
echo "--"
gcloud compute addresses list --project "$cf_proj" \
  --format="table[no-heading](name,address,region.basename(),status)"
echo '```'
echo "ClickHouse IP access list must contain the NAT IP of \`canonflow-runtime\`."
echo
echo '## Secrets (names only)'
echo '```'
gcloud secrets list --project "$cf_proj" --format="value(name)"
echo '```'
echo
echo '## Artifact Registry (latest tags)'
echo '```'
for r in canonflow canonflow-services; do
  echo "-- $r"
  gcloud artifacts docker images list "europe-west4-docker.pkg.dev/$cf_proj/$r" \
    --project "$cf_proj" --include-tags --sort-by="~UPDATE_TIME" \
    --format="value(package.basename(),tags,updateTime.date('%Y-%m-%d'))" 2>/dev/null | head -6
done
echo '```'
echo
echo '## Local artifacts'
echo '```'
echo "var/runs:        $(ls -1 var/runs 2>/dev/null | wc -l) dirs, $(du -sh var/runs 2>/dev/null | cut -f1)"
echo "snapshot beats:  $(ls -1 agents/canonflow_agent/ui/snapshot/beats 2>/dev/null | wc -l) files"
echo "web bundle:      $(du -sh agents/canonflow_agent/ui/web 2>/dev/null | cut -f1 || echo MISSING)"
echo "attic backups:   $(find docs/attic -type f 2>/dev/null | wc -l) files"
echo '```'
echo
echo '### Snapshot index metrics'
echo '```'
python3 - <<'CF_PY' 2>/dev/null || echo "snapshot/index.json unreadable"
import json, pathlib
p = pathlib.Path("agents/canonflow_agent/ui/snapshot/index.json")
d = json.loads(p.read_text(encoding="utf-8"))
for k in ("generated_at","beat_count","canon_beat_count","shot_count",
          "total_duration_s","canon_duration_s","canon_bound_duration_s",
          "canon_unbound_duration_s","intro_duration_s","showcase_duration_s",
          "media_count","verdicts","ctx_state_errors"):
    if k in d:
        print(f"{k:26} {d[k]}")
print(f"{'segments':26} {[s['segment'] for s in d.get('segments',[])]}")
print(f"{'intro':26} {(d.get('intro') or {}).get('beat_id')}")
CF_PY
echo '```'
echo
echo '## Frontend toolchain'
echo '```'
(cd agents/web 2>/dev/null && npm ls --depth=0 2>/dev/null | tail -n +2) || echo "agents/web missing"
echo '```'
echo
echo '## Open items'
echo "Maintained by hand below this line — the sections above are overwritten on every run."
echo
if [ -f docs/STATE.open.md ]; then cat docs/STATE.open.md; else
  echo "- (none recorded; put manual notes in docs/STATE.open.md)"
fi
} > "$out"

echo "wrote $out ($(wc -l < "$out") lines)"
