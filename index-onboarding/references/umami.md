# Umami Analytics

Load this reference for analytics onboarding when the user uses Umami or no analytics provider has been chosen and Umami credentials are available.

## Rules

- Do not hardcode a specific Umami server URL; read `UMAMI_BASE_URL`, for example an origin plus `/api`.
- Prefer self-hosted Umami admin login when `UMAMI_BASE_URL`, `UMAMI_ADMIN_USERNAME`, and `UMAMI_ADMIN_PASSWORD` are available.
- Use `UMAMI_API_KEY` only as a fallback for Umami Cloud or compatible providers that explicitly support API-key auth.
- If neither self-hosted login credentials nor a Cloud API key are available, skip Umami and continue.
- If only a script URL is available without a website id, do not inject an incomplete script.

## Self-Hosted Login Pattern

```bash
TOKEN=$(curl -sS "$UMAMI_BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  --data "{\"username\":\"$UMAMI_ADMIN_USERNAME\",\"password\":\"$UMAMI_ADMIN_PASSWORD\"}" \
  | jq -r '.token')

curl -sS "$UMAMI_BASE_URL/me/websites" \
  -H "Authorization: Bearer $TOKEN"
```

If the account is an admin and site creation or full lookup is needed, use documented admin endpoints such as `GET <UMAMI_BASE_URL>/admin/websites`.

## Minimum Goal

- analytics site/project exists for the root domain
- correct analytics script is wired into the repo
- deployment is triggered if code changed and deployment credentials exist
- live HTML on the final domain includes the expected script URL and site/project id

For static sites, inject the script into the HTML entry point. For env-driven repos, wire `NEXT_PUBLIC_UMAMI_WEBSITE_ID` and `NEXT_PUBLIC_UMAMI_SCRIPT` or the repo's existing analytics env names.
