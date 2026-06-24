#!/usr/bin/env bash
set -euo pipefail

mode="${1:-status}"
profile="${2:-${JZ_DAILY_CHROME_PROFILE:-Profile 6}}"

chrome_app="${JZ_CHROME_APP:-Google Chrome}"
agent_user_data_dir="${JZ_AGENT_CHROME_USER_DATA_DIR:-$HOME/.chrome-codex-automation}"
agent_port="${JZ_AGENT_CHROME_PORT:-9333}"

usage() {
  cat <<'USAGE'
Usage:
  launch-chrome.sh daily [profile-directory]
  launch-chrome.sh agent
  launch-chrome.sh status

Environment:
  JZ_DAILY_CHROME_PROFILE          Default daily profile directory. Default: Profile 6
  JZ_CHROME_APP                    Chrome app name. Default: Google Chrome
  JZ_AGENT_CHROME_USER_DATA_DIR    Agent Chrome user data dir. Default: $HOME/.chrome-codex-automation
  JZ_AGENT_CHROME_PORT             Agent Chrome CDP port. Default: 9333
USAGE
}

launch_daily() {
  open -na "$chrome_app" --args \
    --profile-directory="$profile" \
    --no-first-run \
    --no-default-browser-check
}

launch_agent() {
  open -na "$chrome_app" -g --args \
    --user-data-dir="$agent_user_data_dir" \
    --remote-debugging-port="$agent_port" \
    --remote-debugging-address=127.0.0.1 \
    --no-first-run \
    --no-default-browser-check \
    --new-window "about:blank"
}

show_status() {
  echo "Chrome main processes:"
  pgrep -fl 'Google Chrome.app/Contents/MacOS/Google Chrome' || true
  echo

  echo "Listening CDP ports:"
  lsof -nP -iTCP:"$agent_port" -sTCP:LISTEN || true
  echo

  echo "Default Chrome SingletonLock:"
  default_dir="$HOME/Library/Application Support/Google/Chrome"
  if [[ -L "$default_dir/SingletonLock" ]]; then
    readlink "$default_dir/SingletonLock"
  else
    echo "not found"
  fi
  echo

  echo "Agent Chrome SingletonLock:"
  if [[ -L "$agent_user_data_dir/SingletonLock" ]]; then
    readlink "$agent_user_data_dir/SingletonLock"
  else
    echo "not found"
  fi
}

case "$mode" in
  daily)
    launch_daily
    ;;
  agent)
    launch_agent
    ;;
  status)
    show_status
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown mode: $mode" >&2
    usage >&2
    exit 2
    ;;
esac
