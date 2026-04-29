# Cloudflare Email Routing

Load this reference only when the user explicitly asks for inbound domain email forwarding.

## Preconditions

- final custom domain is delegated to Cloudflare
- Cloudflare zone is active
- forwarding destination is provided or already configured
- Cloudflare token or browser session has Email Routing permission

## Flow

1. Check Email Routing status for the zone.
2. If Email Routing is disabled, enable it and let Cloudflare add MX, SPF, and DKIM records.
3. Check whether the destination mailbox already exists as a verified Email Routing address.
4. If not verified, create the destination address and complete mailbox verification.
5. Update the catch-all rule from `drop` to `forward`.
6. Verify the catch-all rule points to the intended destination.
7. If a sender is available, send a real test email and report the result.

## Completion

Email forwarding is complete only when:

- Email Routing is `enabled`
- MX records point to Cloudflare mail exchangers
- required SPF and DKIM records exist
- catch-all rule is enabled and forwards to the intended mailbox
- test send status is known if a sender is available

If API token scope is insufficient, fall back to browser automation or report the exact missing permission.
