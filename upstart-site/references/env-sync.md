# Production Env Sync

Load this reference only when production env vars are required for the Vercel deployment.

## Source Selection

Do not upload every local env var.

Start from:

- `.env.production` if present
- otherwise `.env`
- otherwise `.env.example` only as a key reference, not as a source of secrets

Sync only variables required for production build and runtime.

Typical examples:

- `NEXT_PUBLIC_APP_URL`
- auth secrets and callback URLs
- database connection string
- analytics public keys
- third-party OAuth credentials

## Commands

Check current production env:

```bash
vercel env ls production --scope <team>
```

Add or update a key:

```bash
printf '%s' '<value>' | vercel env add <KEY> production --scope <team> --yes --force
```

If a required value is missing, stop and report the exact key name. Do not invent secret values.
