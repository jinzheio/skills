#!/usr/bin/env bash
set -euo pipefail

AUTO_PR_DISPATCH_VERSION="0.3.7"

usage() {
  cat <<'USAGE'
Usage: jz-auto-pr-dispatch --repo OWNER/REPO --issue NUMBER [--actor LOGIN] [--base-branch BRANCH]
       jz-auto-pr-dispatch --version
USAGE
}

repo=""
issue=""
actor="${GITHUB_ACTOR:-unknown}"
base_branch="${AUTO_PR_BASE_BRANCH:-main}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      repo="${2:-}"
      shift 2
      ;;
    --issue)
      issue="${2:-}"
      shift 2
      ;;
    --actor)
      actor="${2:-unknown}"
      shift 2
      ;;
    --base-branch)
      base_branch="${2:-main}"
      shift 2
      ;;
    --version)
      printf '%s\n' "$AUTO_PR_DISPATCH_VERSION"
      exit 0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$repo" ] || [ -z "$issue" ]; then
  usage >&2
  exit 2
fi

config_dir="${AUTO_PR_CONFIG_DIR:-$HOME/.config/skills/jz-set-auto-pr}"
state_dir="${AUTO_PR_STATE_DIR:-$HOME/.local/state/jz-set-auto-pr}"
worktree_root="${AUTO_PR_WORKTREE_ROOT:-$HOME/.local/share/jz-set-auto-pr/worktrees}"
macos_notify="${AUTO_PR_MACOS_NOTIFY:-1}"
auto_pr_notify="${AUTO_PR_NOTIFY:-1}"
notify_script="${AUTO_PR_NOTIFY_SCRIPT:-}"

config="${AUTO_PR_REPOS_CONFIG:-$config_dir/repos.json}"

read_configured_agent() {
  local candidate value
  for candidate in \
    "$config_dir/config.yml" \
    "$config_dir/config.yaml" \
    "$config_dir/config.toml"; do
    if [ -f "$candidate" ]; then
      value="$(awk '
        /^[[:space:]]*agent[[:space:]]*[:=]/ {
          value=$0
          sub(/^[[:space:]]*agent[[:space:]]*[:=][[:space:]]*/, "", value)
          sub(/[[:space:]]*#.*$/, "", value)
          gsub(/^["'\''[:space:]]+|["'\''[:space:]]+$/, "", value)
          print value
          exit
        }
      ' "$candidate")"
      if [ -n "$value" ]; then
        printf '%s\n' "$value"
        return 0
      fi
    fi
  done
}

normalize_agent() {
  local raw="$1"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    ""|codex|openai-codex|codex-cli)
      printf 'codex\n'
      ;;
    claude|claude-code|claude_code|anthropic-claude|anthropic-claude-code)
      printf 'claude-code\n'
      ;;
    *)
      echo "Unsupported AUTO_PR_AGENT: $1" >&2
      echo "Supported values: codex, claude-code" >&2
      exit 2
      ;;
  esac
}

configured_agent="${AUTO_PR_AGENT:-}"
if [ -z "$configured_agent" ]; then
  configured_agent="$(read_configured_agent || true)"
fi
auto_pr_agent="$(normalize_agent "$configured_agent")"
case "$auto_pr_agent" in
  codex)
    agent_cli="codex"
    agent_display_name="Codex"
    branch_prefix="codex"
    ;;
  claude-code)
    agent_cli="claude"
    agent_display_name="Claude Code"
    branch_prefix="claude-code"
    ;;
esac

if ! command -v "$agent_cli" >/dev/null 2>&1; then
  echo "Missing local Auto PR agent CLI: $agent_cli" >&2
  echo "Selected agent: $auto_pr_agent" >&2
  exit 1
fi

send_macos_notification() {
  case "$(printf '%s' "$macos_notify" | tr '[:upper:]' '[:lower:]')" in
    0|false|no|off) return 0 ;;
  esac
  if ! command -v osascript >/dev/null 2>&1; then
    return 0
  fi

  osascript - "$1" "$2" "$3" <<'APPLESCRIPT' >/dev/null 2>&1 || true
on run argv
  set notificationTitle to item 1 of argv
  set notificationSubtitle to item 2 of argv
  set notificationMessage to item 3 of argv
  display notification notificationMessage with title notificationTitle subtitle notificationSubtitle
end run
APPLESCRIPT
}

resolve_notify_script() {
  if [ -n "$notify_script" ]; then
    printf '%s\n' "$notify_script"
    return 0
  fi

  local candidate
  for candidate in \
    "$HOME/.codex/skills/jz-notify/scripts/notify.sh" \
    "$HOME/.agents/skills/jz-notify/scripts/notify.sh" \
    "$HOME/.claude/skills/jz-notify/scripts/notify.sh"; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

send_auto_pr_notification() {
  local notification_title="$1"
  local notification_body="$2"
  case "$(printf '%s' "$auto_pr_notify" | tr '[:upper:]' '[:lower:]')" in
    0|false|no|off) return 0 ;;
  esac

  local script_path
  script_path="$(resolve_notify_script || true)"
  if [ -n "$script_path" ]; then
    "$script_path" "$notification_title" "$notification_body" >>"$log_dir/notify.log" 2>&1 || true
  else
    send_macos_notification "$notification_title" "$repo #$issue" "$notification_body"
  fi
}

sanitize_public_text() {
  perl -pe 's#/(Users|home)/[^\s\]\)"]+#<local-path>#g; s#\b[A-Za-z]:\\[^\s\]\)"]+#<local-path>#g'
}

read_public_last_message() {
  if [ -f "$last_message" ]; then
    sed -n '1,120p' "$last_message" | sanitize_public_text
  fi
}

allowed_owner="${AUTO_PR_ALLOWED_OWNER:-}"
if [ -z "$allowed_owner" ] && [ -f "$config_dir/allowed-owner" ]; then
  allowed_owner="$(tr -d '\r\n' < "$config_dir/allowed-owner")"
fi
if [ -n "$allowed_owner" ]; then
  case "$repo" in
    "$allowed_owner"/*) ;;
    *)
      echo "Refusing repo outside allowed owner: $repo" >&2
      echo "Expected owner: $allowed_owner" >&2
      exit 1
      ;;
  esac
fi

if [ ! -f "$config" ]; then
  echo "Missing repo mapping config: $config" >&2
  exit 1
fi

project_dir="$(jq -er --arg repo "$repo" '.[$repo]' "$config" 2>/dev/null || true)"
if [ -z "$project_dir" ]; then
  echo "Repo is not mapped in dispatcher config: $repo" >&2
  echo "Checked: $config" >&2
  exit 1
fi

if ! git -C "$project_dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Mapped project is not a git checkout: $project_dir" >&2
  exit 1
fi

resolved_remote="$(git -C "$project_dir" remote get-url origin 2>/dev/null || true)"
case "$resolved_remote" in
  *"$repo"*) ;;
  *)
    echo "Mapped directory remote does not match $repo: $resolved_remote" >&2
    exit 1
    ;;
esac

lock_name="$(printf '%s' "$repo" | tr '/[:upper:]' '__[:lower:]')"
lock_dir="$state_dir/locks/$lock_name.lock"
mkdir -p "$(dirname "$lock_dir")"
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "Another auto-pr run is already active for $repo" >&2
  exit 1
fi
trap 'rmdir "$lock_dir" 2>/dev/null || true' EXIT

run_id="$(date -u +%Y%m%dT%H%M%SZ)-$lock_name-issue-$issue"
log_dir="$state_dir/logs/$run_id"
mkdir -p "$log_dir"

issue_json="$log_dir/issue.json"
prompt_file="$log_dir/prompt.md"
last_message="$log_dir/last-message.md"
agent_log="$log_dir/$auto_pr_agent.log"
agent_github_token="${AUTO_PR_GITHUB_TOKEN:-}"
if [ -z "$agent_github_token" ] && [ -f "$config_dir/github-token" ]; then
  agent_github_token="$(tr -d '\r\n' < "$config_dir/github-token")"
fi

gh issue view "$issue" \
  --repo "$repo" \
  --json number,title,body,labels,url,author \
  > "$issue_json"

title="$(jq -r '.title' "$issue_json")"
url="$(jq -r '.url' "$issue_json")"
labels="$(jq -r '[.labels[].name] | join(", ")' "$issue_json")"

short_stamp="$(printf '%s' "$run_id" | cut -d- -f1)"
branch="$branch_prefix/issue-${issue}-auto-pr-${short_stamp}"
repo_leaf="${repo##*/}"
worktree_dir="$worktree_root/${repo_leaf}/issue-${issue}-${short_stamp}"
mkdir -p "$(dirname "$worktree_dir")"

git -C "$project_dir" fetch origin "$base_branch" --prune
git -C "$project_dir" worktree add -B "$branch" "$worktree_dir" "origin/$base_branch"

gh issue comment "$issue" \
  --repo "$repo" \
  --body "Auto PR trigger accepted on $(date -u '+%Y-%m-%d %H:%M:%S UTC').

Trigger actor: @$actor
Labels: ${labels:-none}
Branch: \`$branch\`
Agent: \`$auto_pr_agent\`
Log id: \`$run_id\`"

send_macos_notification \
  "Auto PR started" \
  "$repo #$issue" \
  "${title:-Branch: $branch}"

cat > "$prompt_file" <<PROMPT
You are running from a GitHub self-hosted runner trigger.

Repository: $repo
Mapped project directory: $project_dir
Active worktree directory: $worktree_dir
Active branch: $branch
Base branch: $base_branch
Issue: #$issue
Issue URL: $url
Issue title: $title

Task:
Handle exactly this issue and create a pull request. Do not scan for or process other issues.

Required startup:
1. Read \$HOME/Projects/aboutme/about.md if available.
2. Read this repository's AGENTS.md / CLAUDE.md / README guidance before changing files.
3. If the change affects visual design, page layout, components, UX copy, public product copy, README, docs, prompts, templates, or other user-facing text, read \$HOME/Projects/aboutme/voice.md and \$HOME/Projects/aboutme/anti-style.md if available, and do a final writing review before delivery.
4. Confirm repo root and origin. Only operate on $repo.

Implementation rules:
- You are already running from a fresh auto-pr branch/worktree. Use the current branch.
- Do not push the base branch.
- Do not deploy production.
- Use the repo's package manager. For JS/TS projects, prefer pnpm.
- Make the minimum necessary change for issue #$issue.
- Run relevant verification, preferably typecheck/test/build when feasible.
- Commit the fix.
- Push the branch.
- Create a GitHub PR with a body containing summary, verification, docs result, risks/unverified items, and "Closes #$issue".
- If the repository asks for document-release before merging, note that in the PR body. Do not merge.
- Do not include local absolute paths in PR bodies, issue comments, or final messages. Use repo-relative paths.

Issue body follows:

$(jq -r '.body // ""' "$issue_json")
PROMPT

run_agent() {
  case "$auto_pr_agent" in
    codex)
      "$agent_cli" \
        --sandbox danger-full-access \
        --ask-for-approval never \
        exec \
        --cd "$worktree_dir" \
        --output-last-message "$last_message" \
        < "$prompt_file"
      ;;
    claude-code)
      (
        cd "$worktree_dir"
        "$agent_cli" \
          --dangerously-skip-permissions \
          --print \
          "$(cat "$prompt_file")"
      )
      ;;
  esac
}

set +e
if [ -n "$agent_github_token" ]; then
  GH_TOKEN="$agent_github_token" GITHUB_TOKEN="$agent_github_token" run_agent \
    2>&1 | tee "$agent_log"
else
  (unset GH_TOKEN GITHUB_TOKEN; run_agent) \
    2>&1 | tee "$agent_log"
fi
status="${PIPESTATUS[0]}"
set -e

if [ "$auto_pr_agent" = "claude-code" ] && [ -f "$agent_log" ]; then
  sed -n '1,120p' "$agent_log" > "$last_message"
fi

if [ "$status" -eq 0 ]; then
  final_body="Auto PR run completed for issue #$issue.

Log id: \`$run_id\`
Agent: \`$auto_pr_agent\`

$agent_display_name final message:
$(read_public_last_message)"
  send_auto_pr_notification \
    "Auto PR completed" \
    "$repo #$issue
${title:-Branch: $branch}"
else
  final_body="Auto PR run failed for issue #$issue.

Exit code: \`$status\`
Log id: \`$run_id\`
Agent: \`$auto_pr_agent\`

$agent_display_name final message, if any:
$(read_public_last_message)"
  send_auto_pr_notification \
    "Auto PR failed" \
    "$repo #$issue
${title:-Exit code: $status}"
fi

gh issue comment "$issue" --repo "$repo" --body "$final_body" || true
exit "$status"
