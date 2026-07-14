#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="jz-manage-litellm"
CONFIG_PATH="${JZ_LITELLM_OPS_ENV:-$HOME/.config/skills/${SKILL_NAME}/.env}"

if [ -f "$CONFIG_PATH" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$CONFIG_PATH"
  set +a
fi

require() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required config: ${name}" >&2
    echo "Create ~/.config/skills/${SKILL_NAME}/.env from .env.example." >&2
    exit 2
  fi
}

require LITELLM_SSH_HOST
require LITELLM_SSH_USER
require LITELLM_REMOTE_DIR

LITELLM_SSH_PORT="${LITELLM_SSH_PORT:-22}"
LITELLM_POSTGRES_CONTAINER="${LITELLM_POSTGRES_CONTAINER:-litellm-postgres}"
LITELLM_POSTGRES_USER="${LITELLM_POSTGRES_USER:-litellm}"
LITELLM_POSTGRES_DB="${LITELLM_POSTGRES_DB:-litellm}"
LITELLM_COMPOSE_SERVICE="${LITELLM_COMPOSE_SERVICE:-litellm}"
LITELLM_LOCAL_UI_URL="${LITELLM_LOCAL_UI_URL:-http://127.0.0.1:4000/ui/}"
LITELLM_TAILSCALE_UI_URL="${LITELLM_TAILSCALE_UI_URL:-}"

SSH_ARGS=(-p "$LITELLM_SSH_PORT" -o BatchMode=yes -o ConnectTimeout=12)
if [ -n "${LITELLM_SSH_IDENTITY_FILE:-}" ]; then
  identity_file="$LITELLM_SSH_IDENTITY_FILE"
  case "$identity_file" in
    "~/"*) identity_file="$HOME/${identity_file#\~/}" ;;
  esac
  SSH_ARGS+=(-i "$identity_file")
fi

remote() {
  ssh "${SSH_ARGS[@]}" "${LITELLM_SSH_USER}@${LITELLM_SSH_HOST}" "$@"
}

psql_remote() {
  local sql="$1"
  printf '%s\n' "$sql" | remote "cd '$LITELLM_REMOTE_DIR' && docker exec -i $LITELLM_POSTGRES_CONTAINER psql -U '$LITELLM_POSTGRES_USER' -d '$LITELLM_POSTGRES_DB' -P pager=off -F \$'\t' -A"
}

sql_literal() {
  local value="$1"
  value="${value//\'/\'\'}"
  printf "'%s'" "$value"
}

cmd="${1:-help}"
arg="${2:-}"

case "$cmd" in
  help|-h|--help)
    cat <<EOF
Usage: litellm_ops.sh <command> [arg]

Commands:
  status          Check containers, ports, UI and recent logs
  ui              Print configured UI URLs and test remote local UI
  prices          List model prices
  keys            Summarize key statuses and usable keys
  key <alias>     Show one key alias status
  spend           Show recent spend logs
  fallback        Show router fallback settings
EOF
    ;;

  status)
    remote "cd '$LITELLM_REMOTE_DIR' && \
echo '--- compose ---' && docker compose ps && \
echo '--- ui ---' && curl -sS -o /tmp/litellm-ui.out -w 'status=%{http_code} bytes=%{size_download} time=%{time_total}\n' --max-time 12 '$LITELLM_LOCAL_UI_URL' || true && \
echo '--- ports ---' && ss -ltnp | grep -E ':4000|:443|:80' || true && \
echo '--- logs ---' && docker compose logs --tail=120 '$LITELLM_COMPOSE_SERVICE'"
    ;;

  ui)
    if [ -n "$LITELLM_TAILSCALE_UI_URL" ]; then
      echo "tailscale_ui=${LITELLM_TAILSCALE_UI_URL}"
    fi
    echo "remote_local_ui=${LITELLM_LOCAL_UI_URL}"
    remote "curl -sS -o /tmp/litellm-ui.out -w 'status=%{http_code} bytes=%{size_download} time=%{time_total}\n' --max-time 12 '$LITELLM_LOCAL_UI_URL' || true"
    ;;

  prices)
    psql_remote "SELECT model_name, litellm_params->>\$\$input_cost_per_token\$\$ AS input_per_token, litellm_params->>\$\$output_cost_per_token\$\$ AS output_per_token, litellm_params->>\$\$cache_read_input_token_cost\$\$ AS cache_read_per_token, litellm_params->>\$\$cache_creation_input_token_cost\$\$ AS cache_create_per_token FROM \"LiteLLM_ProxyModelTable\" ORDER BY model_name;"
    ;;

  keys)
    psql_remote "WITH course_models AS (SELECT ARRAY[\$\$course-deepseek\$\$,\$\$course-fast\$\$,\$\$course-glm\$\$,\$\$course-kimi\$\$,\$\$course-long\$\$,\$\$course-minimax\$\$]::text[] AS models), token_scope AS (SELECT v.key_name, v.key_alias, t.team_alias, v.last_active, v.spend, v.max_budget, v.expires, COALESCE(v.blocked,false) AS key_blocked, COALESCE(t.blocked,false) AS team_blocked, t.spend AS team_spend, t.max_budget AS team_max_budget, CASE WHEN v.models IS NOT NULL AND cardinality(v.models)>0 THEN v.models WHEN t.models IS NOT NULL AND cardinality(t.models)>0 THEN t.models ELSE ARRAY[]::text[] END AS effective_models FROM \"LiteLLM_VerificationToken\" v LEFT JOIN \"LiteLLM_TeamTable\" t ON t.team_id = v.team_id), judged AS (SELECT *, CASE WHEN effective_models IS NULL OR cardinality(effective_models)=0 THEN (SELECT models FROM course_models) ELSE ARRAY(SELECT unnest(effective_models) INTERSECT SELECT unnest((SELECT models FROM course_models))) END AS accessible_course_models FROM token_scope), classified AS (SELECT *, COALESCE(key_alias,key_name,\$\$(no alias)\$\$) AS alias, CASE WHEN key_blocked OR team_blocked THEN \$\$blocked\$\$ WHEN expires IS NOT NULL AND expires < now() THEN \$\$expired\$\$ WHEN max_budget IS NOT NULL AND spend >= max_budget THEN \$\$key_budget_exhausted\$\$ WHEN team_max_budget IS NOT NULL AND team_spend >= team_max_budget THEN \$\$team_budget_exhausted\$\$ WHEN cardinality(accessible_course_models)=0 THEN \$\$no_course_model_access\$\$ ELSE \$\$usable\$\$ END AS status FROM judged) SELECT status, count(*) FROM classified GROUP BY status ORDER BY status; SELECT alias, team_alias, round(spend::numeric,4) AS spend, max_budget, last_active, CASE WHEN effective_models IS NULL OR cardinality(effective_models)=0 THEN \$\$ALL_MODELS\$\$ ELSE array_to_string(effective_models,\$\$,\$\$) END AS effective_models FROM classified WHERE status=\$\$usable\$\$ ORDER BY alias;"
    ;;

  key)
    if [ -z "$arg" ]; then
      echo "Usage: litellm_ops.sh key <alias>" >&2
      exit 2
    fi
    key_arg="$(sql_literal "$arg")"
    psql_remote "SELECT key_alias, key_name, team_id, spend, max_budget, expires, COALESCE(blocked,false) AS blocked, models, last_active FROM \"LiteLLM_VerificationToken\" WHERE key_alias = $key_arg OR key_name = $key_arg;"
    ;;

  spend)
    psql_remote "SELECT \"startTime\", model_group, spend, prompt_tokens, completion_tokens, metadata->>\$\$user_api_key_alias\$\$ AS key_alias, status FROM \"LiteLLM_SpendLogs\" ORDER BY \"startTime\" DESC LIMIT 30;"
    ;;

  fallback)
    psql_remote "SELECT jsonb_pretty(param_value) FROM \"LiteLLM_Config\" WHERE param_name=\$\$router_settings\$\$;"
    ;;

  *)
    echo "Unknown command: $cmd" >&2
    exit 2
    ;;
esac
