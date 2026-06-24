#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="jz-newapi-ops"
CONFIG_DIR="${JZ_NEWAPI_OPS_CONFIG_DIR:-$HOME/.config/skills/${SKILL_NAME}}"
CONFIG_PATH="${JZ_NEWAPI_OPS_ENV:-$CONFIG_DIR/.env}"
FALLBACK_PLAN="${JZ_NEWAPI_FALLBACK_PLAN:-$CONFIG_DIR/fallback-plan.json}"

if [ -f "$CONFIG_PATH" ]; then
  # shellcheck disable=SC1090
  set -a
  source "$CONFIG_PATH"
  set +a
fi

NEWAPI_REMOTE_DIR="${NEWAPI_REMOTE_DIR:-/opt/new-api}"
NEWAPI_DB="${NEWAPI_DB:-$NEWAPI_REMOTE_DIR/data/one-api.db}"
NEWAPI_LOCAL_UI="${NEWAPI_LOCAL_UI:-http://127.0.0.1:3001}"
NEWAPI_SSH_PORT="${NEWAPI_SSH_PORT:-22}"
NEWAPI_SSH_USER="${NEWAPI_SSH_USER:-}"
NEWAPI_MANAGED_TAG="${NEWAPI_MANAGED_TAG:-managed}"
NEWAPI_FALLBACK_TAG="${NEWAPI_FALLBACK_TAG:-fallback-generated}"
NEWAPI_MODEL_NAME_FILTER="${NEWAPI_MODEL_NAME_FILTER:-%}"
NEWAPI_API_KEY_ENV_NAME="${NEWAPI_API_KEY_ENV_NAME:-LITELLM_LONG_RUN_KEY}"

require() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required config: $name" >&2
    echo "Put private config in $CONFIG_PATH." >&2
    exit 2
  fi
}

sql_quote() {
  local value="$1"
  value="${value//\'/\'\'}"
  printf "'%s'" "$value"
}

json_compact() {
  jq -c . <<<"$1"
}

ssh_target() {
  require NEWAPI_SSH_HOST
  if [ -n "$NEWAPI_SSH_USER" ]; then
    printf '%s@%s' "$NEWAPI_SSH_USER" "$NEWAPI_SSH_HOST"
  else
    printf '%s' "$NEWAPI_SSH_HOST"
  fi
}

ssh_args() {
  local args=(-p "$NEWAPI_SSH_PORT" -o BatchMode=yes -o ConnectTimeout=12)
  if [ -n "${NEWAPI_SSH_IDENTITY_FILE:-}" ]; then
    local identity_file="$NEWAPI_SSH_IDENTITY_FILE"
    case "$identity_file" in
      "~/"*) identity_file="$HOME/${identity_file#\~/}" ;;
    esac
    args+=(-i "$identity_file")
  fi
  printf '%s\0' "${args[@]}"
}

remote() {
  local target
  target="$(ssh_target)"
  local -a args
  while IFS= read -r -d '' arg; do args+=("$arg"); done < <(ssh_args)
  ssh "${args[@]}" "$target" "$@"
}

remote_bash() {
  local target
  target="$(ssh_target)"
  local -a args
  while IFS= read -r -d '' arg; do args+=("$arg"); done < <(ssh_args)
  ssh "${args[@]}" "$target" "bash -s"
}

sqlite_remote() {
  local sql="$1"
  printf '%s\n' "$sql" | remote "sqlite3 -header -column '$NEWAPI_DB'"
}

quota_from_usd() {
  local usd="$1"
  awk -v usd="$usd" 'BEGIN { printf "%.0f", usd * 500000 }'
}

read_public_key() {
  if [ -n "${NEWAPI_API_KEY:-}" ]; then
    printf '%s' "$NEWAPI_API_KEY"
    return
  fi
  if [ -n "${NEWAPI_API_KEY_ENV_FILE:-}" ] && [ -f "$NEWAPI_API_KEY_ENV_FILE" ]; then
    awk -F= -v name="$NEWAPI_API_KEY_ENV_NAME" '$1 == name {print $2}' "$NEWAPI_API_KEY_ENV_FILE" | tail -1
  fi
}

backup_db() {
  remote "cd '$NEWAPI_REMOTE_DIR' && backup=\"data/one-api.db.before-change-\$(date +%Y%m%d-%H%M%S)\" && cp data/one-api.db \"\$backup\" && echo \"backup=\$backup\""
}

restart_newapi() {
  remote "cd '$NEWAPI_REMOTE_DIR' && docker compose restart new-api >/dev/null"
}

generate_fallback_sql() {
  if [ ! -f "$FALLBACK_PLAN" ]; then
    echo "Missing fallback plan: $FALLBACK_PLAN" >&2
    exit 2
  fi
  command -v jq >/dev/null || {
    echo "jq is required to apply fallback plan" >&2
    exit 2
  }

  local managed_tag generated_tag retry_times
  managed_tag="$(jq -r --arg d "$NEWAPI_MANAGED_TAG" '.managed_tag // $d' "$FALLBACK_PLAN")"
  generated_tag="$(jq -r --arg d "$NEWAPI_FALLBACK_TAG" '.generated_tag // $d' "$FALLBACK_PLAN")"
  retry_times="$(jq -r '.retry_times // 3' "$FALLBACK_PLAN")"

  printf 'BEGIN;\n\n'
  printf 'DELETE FROM channels WHERE tag = %s;\n\n' "$(sql_quote "$generated_tag")"

  while IFS= read -r item; do
    local channel models mapping priority weight
    channel="$(jq -r '.channel' <<<"$item")"
    models="$(jq -r '.models' <<<"$item")"
    mapping="$(jq -c '.model_mapping' <<<"$item")"
    priority="$(jq -r '.priority // 100' <<<"$item")"
    weight="$(jq -r '.weight // 10' <<<"$item")"
    printf 'UPDATE channels SET priority = %s, weight = %s, models = %s, model_mapping = %s WHERE tag = %s AND name = %s;\n' \
      "$priority" "$weight" "$(sql_quote "$models")" "$(sql_quote "$mapping")" "$(sql_quote "$managed_tag")" "$(sql_quote "$channel")"
  done < <(jq -c '.primary[]?' "$FALLBACK_PLAN")

  printf '\n'

  while IFS= read -r route; do
    local model source_channel name mapping priority remark
    model="$(jq -r '.model' <<<"$route")"
    source_channel="$(jq -r '.source_channel' <<<"$route")"
    name="$(jq -r '.name' <<<"$route")"
    mapping="$(jq -c '.model_mapping' <<<"$route")"
    priority="$(jq -r '.priority // 90' <<<"$route")"
    remark="generated fallback: ${model} -> ${source_channel}"
    printf 'INSERT INTO channels (type, key, open_ai_organization, test_model, status, name, weight, created_time, test_time, response_time, base_url, other, balance, balance_updated_time, models, "group", used_quota, model_mapping, status_code_mapping, priority, auto_ban, other_info, tag, setting, param_override, header_override, remark, channel_info, settings)\n'
    printf 'SELECT type, key, open_ai_organization, %s, status, %s, weight, strftime('\''%%s'\'','\''now'\''), test_time, response_time, base_url, other, balance, balance_updated_time, %s, "group", 0, %s, status_code_mapping, %s, auto_ban, other_info, %s, setting, param_override, header_override, %s, channel_info, settings FROM channels WHERE tag = %s AND name = %s;\n\n' \
      "$(sql_quote "$model")" "$(sql_quote "$name")" "$(sql_quote "$model")" "$(sql_quote "$mapping")" "$priority" "$(sql_quote "$generated_tag")" "$(sql_quote "$remark")" "$(sql_quote "$managed_tag")" "$(sql_quote "$source_channel")"
  done < <(jq -c '.fallbacks[]? as $f | $f.routes[]? | . + {model: $f.model}' "$FALLBACK_PLAN")

  printf 'INSERT INTO options(key, value) VALUES('\''RetryTimes'\'', %s) ON CONFLICT(key) DO UPDATE SET value=excluded.value;\n' "$(sql_quote "$retry_times")"
  printf '\nCOMMIT;\n'
}

cmd="${1:-help}"

case "$cmd" in
  help|-h|--help)
    cat <<EOF
Usage: newapi_ops.sh <command> [args]

Read-only:
  status                 Check Docker, ports and UI
  ui                     Print configured UI URLs and test remote UI
  models                 Query public /v1/models
  channels               List managed/generated channels and mappings
  quotas                 Show users/tokens quota and cron
  fallback               Show fallback channels by priority
  logs                   Show recent request logs
  schema                 Show core SQLite schemas
  compare-formats <model> Compare /messages and /chat/completions
  render-fallback-sql    Render fallback SQL without writing DB

Write:
  apply-fallback-plan
  set-total-quota <user_id> <usd>
  set-daily-quota-cron <token_id> <usd>
EOF
    ;;

  status)
    remote "cd '$NEWAPI_REMOTE_DIR' && \
echo '--- compose ---' && docker compose ps && \
echo '--- ui local ---' && curl -sS -o /tmp/newapi-ui.out -w 'status=%{http_code} bytes=%{size_download} time=%{time_total}\n' --max-time 12 '$NEWAPI_LOCAL_UI' || true && \
echo '--- ports ---' && ss -ltnp | grep -E ':3000|:3001' || true && \
echo '--- logs ---' && docker compose logs --tail=80 new-api"
    ;;

  ui)
    echo "public_api=${NEWAPI_PUBLIC_BASE:-}"
    echo "tailscale_ui=${NEWAPI_TAILSCALE_UI:-}"
    echo "remote_local_ui=${NEWAPI_LOCAL_UI}"
    remote "curl -sS -o /tmp/newapi-ui.out -w 'remote_local_ui_status=%{http_code} bytes=%{size_download} time=%{time_total}\n' --max-time 12 '$NEWAPI_LOCAL_UI' || true"
    ;;

  models)
    require NEWAPI_PUBLIC_BASE
    key="$(read_public_key || true)"
    if [ -z "${key:-}" ]; then
      echo "Missing NEWAPI_API_KEY or $NEWAPI_API_KEY_ENV_NAME in NEWAPI_API_KEY_ENV_FILE" >&2
      exit 2
    fi
    curl -sS --max-time 20 -H "Authorization: Bearer $key" "$NEWAPI_PUBLIC_BASE/models" | jq -r '.data[].id' | sort
    ;;

  channels)
    sqlite_remote "select id,name,type,status,\"group\",weight,priority,auto_ban,models,model_mapping,tag,remark from channels where tag in ('$(sql_quote "$NEWAPI_MANAGED_TAG" | tr -d "'")','$(sql_quote "$NEWAPI_FALLBACK_TAG" | tr -d "'")') or name like '$(sql_quote "$NEWAPI_MODEL_NAME_FILTER" | tr -d "'")' order by models, priority desc, id;"
    ;;

  quotas)
    remote "set -e
echo '--- tokens ---'
sqlite3 -header -column '$NEWAPI_DB' \"select id,name,remain_quota,used_quota,unlimited_quota,expired_time,model_limits_enabled,model_limits from tokens order by id;\"
echo '--- users ---'
sqlite3 -header -column '$NEWAPI_DB' \"select id,username,quota,used_quota,status,\\\"group\\\" from users order by id;\"
echo '--- cron ---'
crontab -l 2>/dev/null | grep -n 'reset-.*token.*quota\\|new-api' || true
echo '--- reset scripts ---'
find '$NEWAPI_REMOTE_DIR' -maxdepth 1 -type f -name '*quota*.sh' -print -exec sed -n '1,120p' {} \\;"
    ;;

  fallback)
    sqlite_remote "select models,name,model_mapping,priority,status,tag,remark from channels where tag in ('$(sql_quote "$NEWAPI_MANAGED_TAG" | tr -d "'")','$(sql_quote "$NEWAPI_FALLBACK_TAG" | tr -d "'")') order by models, priority desc, id;"
    ;;

  logs)
    sqlite_remote "select id,created_at,model_name,channel_id,prompt_tokens,completion_tokens,use_time,is_stream,substr(other,1,1200) as other from logs order by id desc limit 20;"
    ;;

  schema)
    remote "sqlite3 '$NEWAPI_DB' '.schema channels'; sqlite3 '$NEWAPI_DB' '.schema tokens'; sqlite3 '$NEWAPI_DB' '.schema users'; sqlite3 '$NEWAPI_DB' '.schema options';"
    ;;

  compare-formats)
    model="${2:-}"
    if [ -z "$model" ]; then
      echo "Usage: newapi_ops.sh compare-formats <model>" >&2
      exit 2
    fi
    require NEWAPI_PUBLIC_BASE
    key="$(read_public_key || true)"
    if [ -z "${key:-}" ]; then
      echo "Missing NEWAPI_API_KEY or $NEWAPI_API_KEY_ENV_NAME in NEWAPI_API_KEY_ENV_FILE" >&2
      exit 2
    fi
    python3 - "$NEWAPI_PUBLIC_BASE" "$key" "$model" <<'PY'
import json
import statistics
import sys
import time
import urllib.request

base, key, model = sys.argv[1:4]
tests = [
    (
        "anthropic",
        "/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        {"model": model, "max_tokens": 80, "messages": [{"role": "user", "content": "只回复 OK"}]},
    ),
    (
        "openai",
        "/chat/completions",
        {"Authorization": "Bearer " + key},
        {"model": model, "max_tokens": 80, "temperature": 1, "messages": [{"role": "user", "content": "只回复 OK"}]},
    ),
]

for label, path, headers, body in tests:
    times = []
    for i in range(3):
        req = urllib.request.Request(
            base.rstrip("/") + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=90) as res:
                data = json.loads(res.read())
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            print(label, i + 1, f"{elapsed:.3f}s", data.get("model"), data.get("usage"))
        except Exception as exc:
            elapsed = time.perf_counter() - start
            print(label, i + 1, f"{elapsed:.3f}s", "ERROR", exc)
    if times:
        print(label, "avg", f"{statistics.mean(times):.3f}s")
PY
    ;;

  render-fallback-sql)
    generate_fallback_sql
    ;;

  set-total-quota)
    user_id="${2:-}"
    usd="${3:-}"
    if [ -z "$user_id" ] || [ -z "$usd" ]; then
      echo "Usage: newapi_ops.sh set-total-quota <user_id> <usd>" >&2
      exit 2
    fi
    quota="$(quota_from_usd "$usd")"
    backup_db
    remote "sqlite3 '$NEWAPI_DB' \"BEGIN; update users set quota=$quota where id=$user_id; COMMIT;\" && sqlite3 -header -column '$NEWAPI_DB' \"select id,username,quota,used_quota from users where id=$user_id;\""
    ;;

  set-daily-quota-cron)
    token_id="${2:-}"
    usd="${3:-}"
    if [ -z "$token_id" ] || [ -z "$usd" ]; then
      echo "Usage: newapi_ops.sh set-daily-quota-cron <token_id> <usd>" >&2
      exit 2
    fi
    daily_quota="$(quota_from_usd "$usd")"
    backup_db
    remote_bash <<REMOTE
set -euo pipefail
cat > "$NEWAPI_REMOTE_DIR/reset-token-${token_id}-quota.sh" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

DB="$NEWAPI_DB"
TOKEN_ID=$token_id
DAILY_QUOTA=$daily_quota

sqlite3 "\$DB" <<SQL
BEGIN;
UPDATE tokens
SET remain_quota = CASE
    WHEN (SELECT quota FROM users WHERE id = tokens.user_id) <= 0 THEN 0
    WHEN (SELECT quota FROM users WHERE id = tokens.user_id) < \${DAILY_QUOTA} THEN (SELECT quota FROM users WHERE id = tokens.user_id)
    ELSE \${DAILY_QUOTA}
  END,
  unlimited_quota = 0
WHERE id = \${TOKEN_ID};
COMMIT;
SQL

now=\$(date '+%Y-%m-%d %H:%M:%S %Z')
state=\$(sqlite3 "\$DB" "select 'token=' || id || ' remain_quota=' || remain_quota || ' user_quota=' || (select quota from users where id=tokens.user_id) from tokens where id=\${TOKEN_ID};")
echo "\$now \$state"
SCRIPT
chmod 700 "$NEWAPI_REMOTE_DIR/reset-token-${token_id}-quota.sh"
"$NEWAPI_REMOTE_DIR/reset-token-${token_id}-quota.sh"
tmp=\$(mktemp)
(crontab -l 2>/dev/null || true) | grep -vF "$NEWAPI_REMOTE_DIR/reset-token-${token_id}-quota.sh" > "\$tmp" || true
echo "5 0 * * * $NEWAPI_REMOTE_DIR/reset-token-${token_id}-quota.sh >> $NEWAPI_REMOTE_DIR/logs/quota-reset.log 2>&1" >> "\$tmp"
crontab "\$tmp"
rm -f "\$tmp"
crontab -l | grep -n "$NEWAPI_REMOTE_DIR/reset-token-${token_id}-quota.sh"
REMOTE
    ;;

  apply-fallback-plan)
    backup_db
    sql="$(generate_fallback_sql)"
    printf '%s\n' "$sql" | remote "sqlite3 '$NEWAPI_DB'"
    restart_newapi
    sleep 4
    sqlite_remote "select models,name,model_mapping,priority,status,tag,remark from channels where tag in ('$(sql_quote "$NEWAPI_MANAGED_TAG" | tr -d "'")','$(sql_quote "$NEWAPI_FALLBACK_TAG" | tr -d "'")') order by models, priority desc, id;"
    ;;

  *)
    echo "Unknown command: $cmd" >&2
    exit 2
    ;;
esac
