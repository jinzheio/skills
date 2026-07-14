#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -n "${JZ_CF_AI_GATEWAY_OPS_ENV:-}" && -f "${JZ_CF_AI_GATEWAY_OPS_ENV}" ]]; then
  # shellcheck disable=SC1090
  source "${JZ_CF_AI_GATEWAY_OPS_ENV}"
elif [[ -f "${HOME}/.config/skills/jz-manage-cloudflare-ai-gateway/.env" ]]; then
  # shellcheck disable=SC1090
  source "${HOME}/.config/skills/jz-manage-cloudflare-ai-gateway/.env"
elif [[ -f ".dev.vars" ]]; then
  # shellcheck disable=SC1091
  source ".dev.vars"
fi

CF_API_BASE="${CF_API_BASE:-https://api.cloudflare.com/client/v4}"
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-${CF_ACCOUNT_ID:-}}"
API_TOKEN="${CLOUDFLARE_API_TOKEN:-${CF_API_TOKEN:-}}"
GATEWAY_ID="${CLOUDFLARE_AI_GATEWAY_ID:-${AI_GATEWAY_ID:-}}"
WORKER_NAME="${WORKER_NAME:-}"
WORKER_VERSION="${WORKER_VERSION:-}"

need() {
  local name="$1"
  local value="$2"
  if [[ -z "${value}" ]]; then
    echo "Missing ${name}. Set it in JZ_CF_AI_GATEWAY_OPS_ENV, ~/.config/skills/jz-manage-cloudflare-ai-gateway/.env, .dev.vars, or the shell." >&2
    exit 2
  fi
}

jq_bin() {
  if command -v jq >/dev/null 2>&1; then
    command -v jq
  elif [[ -x /usr/bin/jq ]]; then
    echo /usr/bin/jq
  else
    echo "jq is required." >&2
    exit 2
  fi
}

api() {
  need CLOUDFLARE_ACCOUNT_ID "${ACCOUNT_ID}"
  need CLOUDFLARE_API_TOKEN "${API_TOKEN}"
  local method="$1"
  local path="$2"
  shift 2
  curl -sS -X "${method}" "${CF_API_BASE}/accounts/${ACCOUNT_ID}${path}" \
    -H "Authorization: Bearer ${API_TOKEN}" \
    -H "Content-Type: application/json" \
    "$@"
}

graphql() {
  need CLOUDFLARE_ACCOUNT_ID "${ACCOUNT_ID}"
  need CLOUDFLARE_API_TOKEN "${API_TOKEN}"
  curl -sS "${CF_API_BASE}/graphql" \
    -H "Authorization: Bearer ${API_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "$1"
}

usage() {
  cat <<'EOF'
Usage:
  cf_ai_gateway_ops.sh gateway
  cf_ai_gateway_ops.sh logs [limit]
  cf_ai_gateway_ops.sh log <log_id>
  cf_ai_gateway_ops.sh spend
  cf_ai_gateway_ops.sh providers
  cf_ai_gateway_ops.sh provider <slug>
  cf_ai_gateway_ops.sh set-provider-base-url <slug> <base_url>
  cf_ai_gateway_ops.sh worker <start_utc> <end_utc> [script_version]
  cf_ai_gateway_ops.sh secrets

Required env:
  CLOUDFLARE_ACCOUNT_ID
  CLOUDFLARE_API_TOKEN

Optional env:
  CLOUDFLARE_AI_GATEWAY_ID=<gateway-id>
  WORKER_NAME=<worker-name>
  WORKER_VERSION=<worker version id>
EOF
}

cmd="${1:-help}"
JQ="$(jq_bin)"

case "${cmd}" in
  gateway)
    need CLOUDFLARE_AI_GATEWAY_ID "${GATEWAY_ID}"
    api GET "/ai-gateway/gateways/${GATEWAY_ID}" |
      "${JQ}" '{success, errors, result: (.result | {id, created_at, modified_at, authentication, collect_logs, log_management, rate_limiting_interval, rate_limiting_limit, rate_limiting_technique, cache_ttl, workers_ai_billing_mode, spend_limits, retry_max_attempts, retry_delay, retry_backoff})}'
    ;;

  logs)
    need CLOUDFLARE_AI_GATEWAY_ID "${GATEWAY_ID}"
    limit="${2:-10}"
    api GET "/ai-gateway/gateways/${GATEWAY_ID}/logs?per_page=${limit}" |
      "${JQ}" '{success, errors, result: [.result[] | {id, created_at, provider, model, path, status_code, success, duration, tokens_in, tokens_out, cost, custom_cost, cached, metadata, request_type, response_content_type}]}'
    ;;

  log)
    need CLOUDFLARE_AI_GATEWAY_ID "${GATEWAY_ID}"
    log_id="${2:-}"
    need log_id "${log_id}"
    api GET "/ai-gateway/gateways/${GATEWAY_ID}/logs/${log_id}" |
      "${JQ}" '{success, errors, result: (.result | {id, created_at, provider, model, path, status_code, success, duration, tokens_in, tokens_out, cost, custom_cost, cached, metadata, request_type, request_content_type, response_content_type, request_size, response_size})}'
    ;;

  spend)
    need CLOUDFLARE_AI_GATEWAY_ID "${GATEWAY_ID}"
    api GET "/ai-gateway/gateways/${GATEWAY_ID}" |
      "${JQ}" '{success, errors, spend_limits: .result.spend_limits, rate_limit: {interval: .result.rate_limiting_interval, limit: .result.rate_limiting_limit, technique: .result.rate_limiting_technique}}'
    ;;

  providers)
    api GET "/ai-gateway/custom-providers" |
      "${JQ}" '{success, errors, result: [.result[] | {id, name, slug, enable, base_url, link, description, created_at, modified_at}]}'
    ;;

  provider)
    slug="${2:-}"
    need slug "${slug}"
    api GET "/ai-gateway/custom-providers" |
      "${JQ}" --arg slug "${slug}" '{success, errors, result: ([.result[] | select(.slug == $slug) | {id, name, slug, enable, base_url, link, description, created_at, modified_at}] | first)}'
    ;;

  set-provider-base-url)
    slug="${2:-}"
    base_url="${3:-}"
    need slug "${slug}"
    need base_url "${base_url}"
    provider_id="$(
      api GET "/ai-gateway/custom-providers" |
        "${JQ}" -r --arg slug "${slug}" '.result[] | select(.slug == $slug) | .id' |
        head -n 1
    )"
    need provider_id "${provider_id}"
    payload="$("${JQ}" -n --arg base_url "${base_url}" '{base_url: $base_url}')"
    api PATCH "/ai-gateway/custom-providers/${provider_id}" --data "${payload}" |
      "${JQ}" '{success, errors, result: (.result | {id, name, slug, enable, base_url, link, description, created_at, modified_at})}'
    ;;

  worker)
    start="${2:-}"
    end="${3:-}"
    script_version="${4:-${WORKER_VERSION}}"
    need start_utc "${start}"
    need end_utc "${end}"
    version_filter=""
    if [[ -n "${script_version}" ]]; then
      version_filter=", scriptVersion: \\\"${script_version}\\\""
    fi
    query_template=$(cat <<'EOF'
{
  "query": "query WorkerInvocations($accountTag: string, $datetimeStart: Time, $datetimeEnd: Time) { viewer { accounts(filter: {accountTag: $accountTag}) { workersInvocationsAdaptive(filter: {datetime_geq: $datetimeStart, datetime_leq: $datetimeEnd__VERSION_FILTER__}, limit: 120, orderBy: [datetime_DESC]) { dimensions { datetime scriptName status coloCode scriptVersion } sum { requests errors subrequests requestDuration wallTime cpuTimeUs } quantiles { requestDurationP50 requestDurationP90 wallTimeP50 wallTimeP90 cpuTimeP50 cpuTimeP90 } } } } }",
  "variables": {
    "accountTag": "__ACCOUNT_ID__",
    "datetimeStart": "__START__",
    "datetimeEnd": "__END__"
  }
}
EOF
)
    query="${query_template/__VERSION_FILTER__/${version_filter}}"
    query="${query/__ACCOUNT_ID__/${ACCOUNT_ID}}"
    query="${query/__START__/${start}}"
    query="${query/__END__/${end}}"
    graphql "${query}" |
      "${JQ}" '{errors, invocations: .data.viewer.accounts[0].workersInvocationsAdaptive}'
    ;;

  secrets)
    need WORKER_NAME "${WORKER_NAME}"
    if ! command -v pnpm >/dev/null 2>&1; then
      echo "pnpm is required for wrangler secret list." >&2
      exit 2
    fi
    CLOUDFLARE_API_TOKEN="${API_TOKEN}" pnpm exec wrangler secret list --name "${WORKER_NAME}"
    ;;

  help|-h|--help)
    usage
    ;;

  *)
    usage >&2
    exit 2
    ;;
esac
