#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="jz-send-notification"
TITLE="${1:-任务完成}"
BODY="${2:-请查看任务结果}"

FEISHU_WEBHOOK="${FEISHU_WEBHOOK_URL:-${LARK_WEBHOOK_URL:-}}"
FEISHU_SIGN_KEY="${FEISHU_SIGN_KEY:-${FEISHU_WEBHOOK_SECRET:-${LARK_SIGN_KEY:-${LARK_WEBHOOK_SECRET:-}}}}"
FEISHU_NOTIFY_METHOD="${FEISHU_NOTIFY_METHOD:-auto}"
LARK_USER_ID="${LARK_USER_ID:-${FEISHU_USER_ID:-}}"
LARK_CHAT_ID="${LARK_CHAT_ID:-${FEISHU_CHAT_ID:-}}"
LARK_SEND_AS="${LARK_SEND_AS:-${FEISHU_SEND_AS:-bot}}"
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"

strip_quotes() {
  local value="$1"
  value="${value%$'\r'}"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "$value"
}

read_env_value() {
  local file="$1"
  local pattern="$2"
  local line
  line="$(grep -E "$pattern" "$file" 2>/dev/null | tail -n 1 || true)"
  [ -n "$line" ] || return 0
  strip_quotes "${line#*=}"
}

load_env_file() {
  local file="$1"
  [ -f "$file" ] || return 0

  local value
  if [ -z "$FEISHU_WEBHOOK" ]; then
    value="$(read_env_value "$file" '^(FEISHU_WEBHOOK_URL|LARK_WEBHOOK_URL)=')"
    [ -z "$value" ] || FEISHU_WEBHOOK="$value"
  fi
  if [ -z "$FEISHU_SIGN_KEY" ]; then
    value="$(read_env_value "$file" '^(FEISHU_SIGN_KEY|FEISHU_WEBHOOK_SECRET|LARK_SIGN_KEY|LARK_WEBHOOK_SECRET)=')"
    [ -z "$value" ] || FEISHU_SIGN_KEY="$value"
  fi
  if [ "$FEISHU_NOTIFY_METHOD" = "auto" ]; then
    value="$(read_env_value "$file" '^FEISHU_NOTIFY_METHOD=')"
    [ -z "$value" ] || FEISHU_NOTIFY_METHOD="$value"
  fi
  if [ -z "$LARK_USER_ID" ]; then
    value="$(read_env_value "$file" '^(LARK_USER_ID|FEISHU_USER_ID)=')"
    [ -z "$value" ] || LARK_USER_ID="$value"
  fi
  if [ -z "$LARK_CHAT_ID" ]; then
    value="$(read_env_value "$file" '^(LARK_CHAT_ID|FEISHU_CHAT_ID)=')"
    [ -z "$value" ] || LARK_CHAT_ID="$value"
  fi
  if [ "$LARK_SEND_AS" = "bot" ]; then
    value="$(read_env_value "$file" '^(LARK_SEND_AS|FEISHU_SEND_AS)=')"
    [ -z "$value" ] || LARK_SEND_AS="$value"
  fi
  if [ -z "$SLACK_WEBHOOK" ]; then
    value="$(read_env_value "$file" '^SLACK_WEBHOOK_URL=')"
    [ -z "$value" ] || SLACK_WEBHOOK="$value"
  fi
}

CONFIG_PATH="${JZ_NOTIFY_ENV:-$HOME/.config/skills/${SKILL_NAME}/.env}"
load_env_file "$CONFIG_PATH"

escape_applescript() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

send_system_notification() {
  if command -v osascript >/dev/null 2>&1; then
    local safe_title safe_body
    safe_title="$(escape_applescript "$TITLE")"
    safe_body="$(escape_applescript "$BODY")"
    osascript -e "display notification \"$safe_body\" with title \"$safe_title\" sound name \"Glass\""
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "$TITLE" "$BODY"
  else
    if [ "$(id -u)" = "0" ]; then
      echo "[notify] ${TITLE}: ${BODY}" | wall 2>/dev/null || true
    fi
    echo "[notify] no desktop notifier, skipped system notification" >&2
  fi
}

feishu_webhook_payload() {
  TITLE="$TITLE" BODY="$BODY" FEISHU_SIGN_KEY="$FEISHU_SIGN_KEY" node -e '
const crypto = require("crypto");
const title = process.env.TITLE || "";
const body = process.env.BODY || "";
const secret = process.env.FEISHU_SIGN_KEY || "";
const payload = {
  msg_type: "text",
  content: { text: `${title}\n${body}` }
};
if (secret) {
  const timestamp = Math.floor(Date.now() / 1000).toString();
  payload.timestamp = timestamp;
  payload.sign = crypto
    .createHmac("sha256", `${timestamp}\n${secret}`)
    .update("")
    .digest("base64");
}
process.stdout.write(JSON.stringify(payload));
'
}

send_feishu_webhook() {
  [ -n "$FEISHU_WEBHOOK" ] || {
    echo "[notify] Feishu webhook not configured" >&2
    return 0
  }
  command -v curl >/dev/null 2>&1 || {
    echo "[notify] curl not found; skipped Feishu webhook" >&2
    return 0
  }
  command -v node >/dev/null 2>&1 || {
    echo "[notify] node not found; skipped Feishu webhook" >&2
    return 0
  }

  local payload response
  payload="$(feishu_webhook_payload)"
  response="$(curl -fsS -X POST -H "Content-Type: application/json" -d "$payload" "$FEISHU_WEBHOOK")" || {
    echo "[notify] Feishu webhook request failed" >&2
    return 0
  }

  RESPONSE="$response" node -e '
const response = process.env.RESPONSE || "";
try {
  const parsed = JSON.parse(response);
  const code = parsed.code ?? parsed.StatusCode;
  if (code === 0) process.exit(0);
  console.error(`[notify] Feishu webhook returned error: ${response}`);
  process.exit(1);
} catch {
  console.error(`[notify] Feishu webhook returned non-JSON response: ${response}`);
  process.exit(1);
}
' || {
    echo "[notify] Feishu webhook failed" >&2
    return 0
  }
}

send_feishu_cli() {
  [ "$FEISHU_NOTIFY_METHOD" != "webhook" ] || return 1
  command -v lark-cli >/dev/null 2>&1 || return 1

  local target_args message open_id
  message="${TITLE}"$'\n'"${BODY}"
  target_args=()

  if [ -n "$LARK_CHAT_ID" ]; then
    target_args=(--chat-id "$LARK_CHAT_ID")
  else
    if [ -z "$LARK_USER_ID" ] && command -v node >/dev/null 2>&1; then
      open_id="$(
        lark-cli auth status --json 2>/dev/null | node -e '
let data = "";
process.stdin.on("data", chunk => data += chunk);
process.stdin.on("end", () => {
  try {
    const parsed = JSON.parse(data);
    process.stdout.write(parsed?.identities?.user?.openId || "");
  } catch {}
});
' || true
      )"
      LARK_USER_ID="$open_id"
    fi

    if [ -n "$LARK_USER_ID" ]; then
      target_args=(--user-id "$LARK_USER_ID")
    fi
  fi

  [ "${#target_args[@]}" -gt 0 ] || return 1
  lark-cli im +messages-send --as "$LARK_SEND_AS" "${target_args[@]}" --text "$message" --format json >/dev/null 2>&1
}

send_feishu_notification() {
  if send_feishu_cli; then
    return 0
  fi
  echo "[notify] Feishu CLI unavailable or failed; trying webhook fallback" >&2
  send_feishu_webhook
}

send_slack_webhook() {
  [ -n "$SLACK_WEBHOOK" ] || {
    echo "[notify] Slack webhook not configured; use Codex Slack connector when available" >&2
    return 0
  }
  command -v curl >/dev/null 2>&1 || {
    echo "[notify] curl not found; skipped Slack webhook" >&2
    return 0
  }
  command -v node >/dev/null 2>&1 || {
    echo "[notify] node not found; skipped Slack webhook" >&2
    return 0
  }

  local payload
  payload="$(
    TITLE="$TITLE" BODY="$BODY" node -e '
const title = process.env.TITLE || "";
const body = process.env.BODY || "";
process.stdout.write(JSON.stringify({ text: `*${title}*\n${body}` }));
'
  )"

  curl -fsS -X POST -H "Content-Type: application/json" -d "$payload" "$SLACK_WEBHOOK" >/dev/null || {
    echo "[notify] Slack webhook failed" >&2
    return 0
  }
}

send_system_notification || true
send_feishu_notification || true
send_slack_webhook || true
