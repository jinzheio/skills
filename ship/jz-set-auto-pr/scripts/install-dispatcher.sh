#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_dir="$(cd "$script_dir/.." && pwd)"
template="$skill_dir/references/jz-auto-pr-dispatch.sh"
target="${AUTO_PR_DISPATCH_PATH:-$HOME/bin/jz-auto-pr-dispatch}"
config_dir="${AUTO_PR_CONFIG_DIR:-$HOME/.config/skills/jz-set-auto-pr}"
legacy_config_dir="${AUTO_PR_LEGACY_CONFIG_DIR:-$HOME/.codex/auto-pr}"

if [ ! -f "$template" ]; then
  echo "Missing dispatcher template: $template" >&2
  exit 1
fi

template_version="$(grep -E '^AUTO_PR_DISPATCH_VERSION=' "$template" | head -1 | cut -d= -f2- | tr -d '"')"
current_version=""
if [ -x "$target" ]; then
  current_version="$("$target" --version 2>/dev/null || true)"
fi

mkdir -p "$(dirname "$target")" "$config_dir"

if [ "$current_version" != "$template_version" ]; then
  install -m 755 "$template" "$target"
  echo "Installed jz-auto-pr-dispatch $template_version at $target"
else
  echo "jz-auto-pr-dispatch $current_version is already up to date at $target"
fi

if [ ! -f "$config_dir/repos.json" ] && [ -f "$legacy_config_dir/repos.json" ]; then
  install -m 600 "$legacy_config_dir/repos.json" "$config_dir/repos.json"
  echo "Copied existing repo mapping config to $config_dir/repos.json"
elif [ ! -f "$config_dir/repos.json" ]; then
  printf '{}\n' > "$config_dir/repos.json"
  chmod 600 "$config_dir/repos.json"
  echo "Created repo mapping config at $config_dir/repos.json"
fi
