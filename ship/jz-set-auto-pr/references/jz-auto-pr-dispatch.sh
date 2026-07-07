#!/usr/bin/env bash
set -euo pipefail

AUTO_PR_DISPATCH_VERSION="0.3.1"

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
legacy_config_dir="${AUTO_PR_LEGACY_CONFIG_DIR:-$HOME/.codex/auto-pr}"
state_dir="${AUTO_PR_STATE_DIR:-$HOME/.local/state/jz-set-auto-pr}"
worktree_root="${AUTO_PR_WORKTREE_ROOT:-$HOME/.local/share/jz-set-auto-pr/worktrees}"

config="${AUTO_PR_REPOS_CONFIG:-$config_dir/repos.json}"
if [ ! -f "$config" ] && [ -f "$legacy_config_dir/repos.json" ]; then
  config="$legacy_config_dir/repos.json"
fi

if [ ! -f "$config" ]; then
  echo "Missing repo mapping config: $config" >&2
  exit 1
fi

project_dir="$(jq -er --arg repo "$repo" '.[$repo]' "$config" 2>/dev/null || true)"
if [ -z "$project_dir" ] && [ "$config" != "$legacy_config_dir/repos.json" ] && [ -f "$legacy_config_dir/repos.json" ]; then
  project_dir="$(jq -er --arg repo "$repo" '.[$repo]' "$legacy_config_dir/repos.json" 2>/dev/null || true)"
fi
if [ -z "$project_dir" ]; then
  echo "Repo is not mapped in dispatcher config: $repo" >&2
  echo "Checked: $config" >&2
  if [ -f "$legacy_config_dir/repos.json" ]; then
    echo "Checked fallback: $legacy_config_dir/repos.json" >&2
  fi
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
codex_log="$log_dir/codex.log"
codex_github_token="${AUTO_PR_GITHUB_TOKEN:-}"
if [ -z "$codex_github_token" ] && [ -f "$config_dir/github-token" ]; then
  codex_github_token="$(tr -d '\r\n' < "$config_dir/github-token")"
elif [ -z "$codex_github_token" ] && [ -f "$legacy_config_dir/github-token" ]; then
  codex_github_token="$(tr -d '\r\n' < "$legacy_config_dir/github-token")"
fi

gh issue view "$issue" \
  --repo "$repo" \
  --json number,title,body,labels,url,author \
  > "$issue_json"

title="$(jq -r '.title' "$issue_json")"
url="$(jq -r '.url' "$issue_json")"
labels="$(jq -r '[.labels[].name] | join(", ")' "$issue_json")"

short_stamp="$(printf '%s' "$run_id" | cut -d- -f1)"
branch="codex/issue-${issue}-auto-pr-${short_stamp}"
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
Log id: \`$run_id\`"

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
- You are already running from a fresh codex/* branch/worktree. Use the current branch.
- Do not push the base branch.
- Do not deploy production.
- Use the repo's package manager. For JS/TS projects, prefer pnpm.
- Make the minimum necessary change for issue #$issue.
- Run relevant verification, preferably typecheck/test/build when feasible.
- Commit the fix.
- Push the branch.
- Create a GitHub PR with a body containing summary, verification, docs result, risks/unverified items, and "Closes #$issue".
- If the repository asks for document-release before merging, note that in the PR body. Do not merge.

Issue body follows:

$(jq -r '.body // ""' "$issue_json")
PROMPT

set +e
if [ -n "$codex_github_token" ]; then
  env GH_TOKEN="$codex_github_token" GITHUB_TOKEN="$codex_github_token" codex \
    --sandbox danger-full-access \
    --ask-for-approval never \
    exec \
    --cd "$worktree_dir" \
    --output-last-message "$last_message" \
    < "$prompt_file" \
    2>&1 | tee "$codex_log"
else
  env -u GH_TOKEN -u GITHUB_TOKEN codex \
    --sandbox danger-full-access \
    --ask-for-approval never \
    exec \
    --cd "$worktree_dir" \
    --output-last-message "$last_message" \
    < "$prompt_file" \
    2>&1 | tee "$codex_log"
fi
status="${PIPESTATUS[0]}"
set -e

if [ "$status" -eq 0 ]; then
  final_body="Auto PR run completed for issue #$issue.

Log id: \`$run_id\`

Codex final message:
$(sed -n '1,120p' "$last_message" 2>/dev/null || true)"
else
  final_body="Auto PR run failed for issue #$issue.

Exit code: \`$status\`
Log id: \`$run_id\`

Codex final message, if any:
$(sed -n '1,120p' "$last_message" 2>/dev/null || true)"
fi

gh issue comment "$issue" --repo "$repo" --body "$final_body" || true
exit "$status"
