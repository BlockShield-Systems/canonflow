#!/usr/bin/env bash
# Build the agent image in Cloud Build and roll out a new Cloud Run revision.
# Load env first:  set -a; . canonflow_agent/.env; set +a

cf_deploy() {
  cf_proj=canonflow-agentic-cinema
  cf_region=europe-west4
  cf_repo=canonflow-services
  cf_service=canonflow-agent
  cf_container=agent

  cd "$(dirname "$0")/.." || { echo "ERROR: cannot enter project root" >&2; return 1; }

  if [ -z "${CF_PROJECT:-}" ]; then
    echo "ERROR: CF_PROJECT is not set. Run: set -a; . canonflow_agent/.env; set +a" >&2
    return 1
  fi

  for cf_req in Dockerfile \
                web/package-lock.json \
                web/public/robots.txt \
                canonflow_agent/ui/snapshot/index.json; do
    if [ ! -f "$cf_req" ]; then
      echo "ERROR: required file missing: $cf_req" >&2
      return 1
    fi
  done

  cf_sha="$(git rev-parse --short=7 HEAD)"
  if [ -z "$cf_sha" ]; then
    echo "ERROR: cannot resolve git HEAD" >&2
    return 1
  fi

  cf_tag="$(date -u +%Y%m%d-%H%M%S)-${cf_sha}"
  cf_img="${cf_region}-docker.pkg.dev/${cf_proj}/${cf_repo}/${cf_service}:${cf_tag}"
  cf_log="$(mktemp -t canonflow-build-XXXXXX.log)"

  echo "== target image: ${cf_img}"
  echo "== build log:    ${cf_log}"

  if gcloud builds submit --tag "${cf_img}" --project "${cf_proj}" . > "${cf_log}" 2>&1; then
    tail -20 "${cf_log}"
  else
    tail -40 "${cf_log}" >&2
    echo "ERROR: Cloud Build failed - no rollout performed. Full log: ${cf_log}" >&2
    return 1
  fi

  echo "== rolling out revision"
  # --format is a global flag and must precede --container,
  # otherwise gcloud treats it as a container-scoped argument.
  if gcloud run services update "${cf_service}" \
       --region "${cf_region}" --project "${cf_proj}" \
       --format="value(status.latestCreatedRevisionName,status.url)" \
       --container "${cf_container}" \
       --image "${cf_img}" \
       --update-env-vars "CF_PROJECT=${CF_PROJECT},GOOGLE_GENAI_USE_ENTERPRISE=false" \
       --remove-env-vars "GOOGLE_GENAI_USE_VERTEXAI"; then
    echo "== deployed image: ${cf_img}"
    rm -f "${cf_log}"
    return 0
  fi

  echo "ERROR: rollout failed. Image is available for a manual retry:" >&2
  echo "       ${cf_img}" >&2
  return 1
}

cf_deploy
