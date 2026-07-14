#!/usr/bin/env bash
set -euo pipefail

OVH_KEY="${OVH_SSH_KEY_PATH:-$HOME/.ssh/id_ed25519_ovh}"
host=""
user=""
user_overridden=false
key_override=""
remote_cmd=""

usage() {
  cat <<USAGE
Usage:
  bash scripts/login-ovh-server.sh --host <ip-or-host> [--user <ssh-user>] [--key <private-key-path>] [--cmd '<command>']

Options:
  --host <ip-or-host>            Server IP or hostname (required)
  --user <ssh-user>              SSH user (default: ubuntu)
  --key <private-key-path>       SSH private key (default: ~/.ssh/id_ed25519_ovh)
  --cmd '<remote-command>'       Execute command and exit (non-interactive)
  -h, --help                     Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      host="${2:-}"; shift 2 ;;
    --user)
      user="${2:-}"; user_overridden=true; shift 2 ;;
    --key)
      key_override="${2:-}"; shift 2 ;;
    --cmd)
      remote_cmd="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$host" ]]; then
  echo "Error: --host is required." >&2
  usage
  exit 1
fi

if [[ "$user_overridden" != "true" ]]; then
  user="ubuntu"
fi

key="${key_override:-$OVH_KEY}"

if [[ ! -f "$key" ]]; then
  echo "Error: SSH key not found: $key" >&2
  echo "Use --key to specify a different path." >&2
  exit 1
fi

chmod 600 "$key" || true

echo "[login-ovh] user=${user} host=${host} key=${key}"

if [[ -n "$remote_cmd" ]]; then
  exec ssh -i "$key" \
    -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout=10 \
    "${user}@${host}" "$remote_cmd"
fi

exec ssh -i "$key" \
  -o StrictHostKeyChecking=accept-new \
  -o ConnectTimeout=10 \
  "${user}@${host}"
