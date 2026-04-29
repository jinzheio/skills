# Microsoft Clarity

Load this reference for Clarity status verification and wiring.

Clarity is project-scoped. Prefer the shared integration map configured by `SITE_INTEGRATIONS_CONFIG`. If the map is missing or lacks Clarity for the target domain, read `CLARITY_ID` and `CLARITY_TOKEN` from the current environment and from the resolved repo's `.env` / `.env.local`.

Microsoft's Clarity MCP server and Data Export API require an existing Clarity project and a project-level Data Export API token. Treat them as analytics read/query tools, not project-creation APIs.

## Sources

1. Resolve the target domain in the integration map.
2. Read `domains[hostname].clarity`.
3. If `clarity.project_id` and `clarity.token` are present, use them.
4. If the map is missing, unreadable, invalid, or lacks Clarity for the target domain, read `CLARITY_ID` and `CLARITY_TOKEN` from the current process environment.
5. If the process environment lacks either value and the repo is resolved, inspect `.env` and `.env.local` in that repo before reporting missing credentials. Parse simple `KEY=value`, quoted, and unquoted forms; avoid sourcing arbitrary dotenv files when they may contain shell syntax that can break parsing.
6. If any source provides both values, verify the live site has the matching Clarity script and query the Data Export API where needed.
7. If neither source provides both values, report Clarity as `skipped` with reason `no clarity credentials`.
8. If the Clarity script is installed but no token is available, report `partial` only if the live script is verifiable; otherwise report `skipped`.

Safe repo-local dotenv presence check:

```bash
for f in .env .env.local; do
  [ -f "$f" ] || continue
  awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{k=$1; v=substr($0,index($0,"=")+1); if (k ~ /^CLARITY_(ID|TOKEN)$/) printf "%s=%s len=%d\n", k, (v=="" ? "empty" : "set"), length(v)}' "$f"
done
```

Trim the project id before injecting it into code or provider envs. Newlines from `printf '%s\n'` or copied UI values can produce a broken `https://www.clarity.ms/tag/<id>\n` script URL.

## Wiring

Install only the public project id in browser/runtime config. Do not send `CLARITY_TOKEN` to Vercel, Next public env vars, client bundles, or deployed serverless envs unless a server-side collector explicitly needs it.

For local Vercel deploys, ensure `.vercelignore` excludes `.env` and `.env.*` while preserving `.env.example` before deploying from a working copy that contains Clarity tokens:

```text
.env
.env.*
!.env.example
```

Do not request Clarity credentials interactively.
Do not use old env names such as `CLARITY_PROJECT_ID` or `CLARITY_API_TOKEN`.
Do not print `CLARITY_TOKEN` in logs or final summaries.

Do not mark Clarity complete unless real project wiring is verifiable.
