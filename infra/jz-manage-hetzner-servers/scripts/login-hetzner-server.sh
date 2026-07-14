#!/usr/bin/env bash
set -euo pipefail

HETZNER_KEY_DEFAULT="${HETZNER_SSH_KEY_PATH:-$HOME/.ssh/id_ed25519_hetz_01}"
host=""
user=""
user_overridden=false
password=""
key_override=""
remote_cmd=""

usage() {
  cat <<USAGE
Usage:
  bash scripts/login-hetzner-server.sh --host <ip> [options]

Options:
  --host <ip-or-host>            Server IP or hostname (required)
  --user <ssh-user>              SSH user (default: root)
  --key <private-key-path>       SSH private key (default: ~/.ssh/id_ed25519_hetz_01)
  --password <root-password>     Root password (fallback when key not available)
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
    --password)
      password="${2:-}"; shift 2 ;;
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
  user="root"
fi

# Try key-based login first
key="${key_override:-$HETZNER_KEY_DEFAULT}"

if [[ -n "$key" && -f "$key" ]]; then
  chmod 600 "$key" || true
  echo "[login-hetzner] Trying key login: user=${user} host=${host} key=${key}"

  if [[ -n "$remote_cmd" ]]; then
    if ssh -i "$key" \
      -o ConnectTimeout=10 \
      -o BatchMode=yes \
      -o StrictHostKeyChecking=accept-new \
      "${user}@${host}" "$remote_cmd" 2>/dev/null; then
      exit 0
    fi
  else
    if ssh -i "$key" \
      -o ConnectTimeout=10 \
      -o BatchMode=yes \
      -o StrictHostKeyChecking=accept-new \
      "${user}@${host}" -t 2>/dev/null; then
      exit 0
    fi
  fi
  echo "[login-hetzner] Key login failed, trying password..."
fi

# Fallback to password
if [[ -z "$password" ]]; then
  echo "Error: No password provided and key login failed." >&2
  echo "Use --password to provide the root password." >&2
  exit 2
fi

echo "[login-hetzner] Password login: user=${user} host=${host}"

ssh_opts=(
  -o PreferredAuthentications=password
  -o PubkeyAuthentication=no
  -o StrictHostKeyChecking=accept-new
  -o ConnectTimeout=10
)

if command -v sshpass >/dev/null 2>&1; then
  if [[ -n "$remote_cmd" ]]; then
    exec sshpass -p "$password" ssh "${ssh_opts[@]}" "${user}@${host}" "$remote_cmd"
  fi
  exec sshpass -p "$password" ssh "${ssh_opts[@]}" "${user}@${host}"
fi

# No sshpass — fall back to SSH's interactive password prompt without printing the password.
echo "[login-hetzner] sshpass not installed. Starting interactive SSH; enter the password at the prompt."
if [[ -n "$remote_cmd" ]]; then
  exec ssh "${ssh_opts[@]}" "${user}@${host}" "$remote_cmd"
fi
exec ssh "${ssh_opts[@]}" "${user}@${host}"
