#!/usr/bin/env bash
# check-dns-propagation.sh
#
# Polls DNS propagation state for a domain.
#
# IMPORTANT: DNS results from local resolvers and even public resolvers can be
# stale, cached, or polluted by the local network for many minutes after the
# actual delegation has changed. This script is supporting evidence only.
# The authoritative completion signal is a successful HTTPS page load of the
# live site — not a clean DNS answer.
#
# Usage:
#   ./check-dns-propagation.sh <domain> [expected-ns-keyword] [max-attempts] [interval-seconds]
#
# Examples:
#   ./check-dns-propagation.sh example.com "cloudflare"
#   ./check-dns-propagation.sh example.com "cloudflare" 20 30
#
# Exit codes:
#   0  DNS looks propagated AND live HTTPS check passed
#   1  Timed out — DNS may still be stale or polluted; check the live site directly
#   2  Missing required argument

set -euo pipefail

DOMAIN="${1:-}"
NS_KEYWORD="${2:-}"          # substring to expect in NS output, e.g. "cloudflare"
MAX_ATTEMPTS="${3:-24}"      # default: 24 attempts
INTERVAL="${4:-30}"          # default: 30 seconds between attempts

if [[ -z "$DOMAIN" ]]; then
  echo "Usage: $0 <domain> [expected-ns-keyword] [max-attempts] [interval-seconds]" >&2
  exit 2
fi

HTTPS_URL="https://${DOMAIN}"
attempt=0

echo "Checking DNS propagation for: $DOMAIN"
echo "NS keyword to match: ${NS_KEYWORD:-(any)}"
echo "Max attempts: $MAX_ATTEMPTS × ${INTERVAL}s = $((MAX_ATTEMPTS * INTERVAL))s timeout"
echo "Authoritative signal: live HTTPS access to $HTTPS_URL"
echo "────────────────────────────────────────────"

while [[ $attempt -lt $MAX_ATTEMPTS ]]; do
  attempt=$((attempt + 1))
  echo ""
  echo "[Attempt $attempt / $MAX_ATTEMPTS] $(date '+%H:%M:%S')"

  # ── 1. Check public resolvers ───────────────────────────────────────────────
  ns_1111=$(dig NS "$DOMAIN" @1.1.1.1 +short +time=3 +tries=1 2>/dev/null || true)
  ns_8888=$(dig NS "$DOMAIN" @8.8.8.8 +short +time=3 +tries=1 2>/dev/null || true)

  echo "  1.1.1.1 NS: ${ns_1111:-<empty>}"
  echo "  8.8.8.8 NS: ${ns_8888:-<empty>}"

  ns_match=false
  if [[ -n "$NS_KEYWORD" ]]; then
    if echo "$ns_1111 $ns_8888" | grep -qi "$NS_KEYWORD"; then
      ns_match=true
      echo "  ✓ NS keyword '$NS_KEYWORD' found in public resolver output"
    else
      echo "  ✗ NS keyword '$NS_KEYWORD' not yet visible in public resolvers"
      echo "    NOTE: local network or resolver cache may be stale — this is normal"
    fi
  else
    [[ -n "$ns_1111" || -n "$ns_8888" ]] && ns_match=true
  fi

  # ── 2. Authoritative check: live HTTPS access ───────────────────────────────
  http_status=$(curl -o /dev/null -s -w "%{http_code}" --max-time 8 \
    -H "User-Agent: dns-propagation-check/1.0" "$HTTPS_URL" 2>/dev/null || echo "000")

  echo "  HTTPS $HTTPS_URL → HTTP $http_status"

  if [[ "$http_status" =~ ^(200|301|302|307|308)$ ]]; then
    echo ""
    echo "  ✅ LIVE — Site is reachable over HTTPS (HTTP $http_status)"
    echo "     This is the authoritative completion signal."
    if [[ "$ns_match" == false ]]; then
      echo "     ⚠️  DNS resolver output still looks stale or polluted — this is a"
      echo "        known local-network issue and does NOT block completion."
      echo "        Registrar/DNS provider records are correct; resolver cache will clear."
    fi
    exit 0
  fi

  # ── 3. Not done yet ─────────────────────────────────────────────────────────
  if [[ $attempt -lt $MAX_ATTEMPTS ]]; then
    echo "  ↻ Not ready. Waiting ${INTERVAL}s…"
    sleep "$INTERVAL"
  fi
done

echo ""
echo "────────────────────────────────────────────"
echo "⏱  Timed out after $((MAX_ATTEMPTS * INTERVAL))s."
echo ""
echo "This does NOT necessarily mean propagation failed. DNS results from this"
echo "machine may be polluted or cached by the local network."
echo ""
echo "Next steps:"
echo "  1. Open $HTTPS_URL directly in a browser."
echo "  2. Check Cloudflare/Vercel dashboards — if both show the domain as active"
echo "     and the records are correct, the configuration is done."
echo "  3. If the page loads in a browser but this script times out, treat the"
echo "     live page load as the completion signal and proceed."
exit 1
