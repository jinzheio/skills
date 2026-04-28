---
name: index-onboarding
description: "Complete post-domain-launch analytics and search indexing setup for a public site on its final custom domain. Use after the site is already live on the intended domain, typically after `upstart-site` and then `new-domain-launch`. Covers Umami or compatible analytics, Google Search Console ownership plus sitemap submission, IndexNow onboarding, Bing Webmaster Tools onboarding, and Clarity status or handoff."
---

# Index Onboarding

Use this skill after the site is already reachable on its final custom domain.

This is not a deployment skill. It is a post-domain-launch onboarding workflow for:

1. Umami or another configured web analytics service
2. Google Search Console
3. IndexNow
4. Bing Webmaster Tools
5. Microsoft Clarity

Intended sequence:

1. `upstart-site`
2. `new-domain-launch`
3. `index-onboarding`

## Use This When

Use this skill when the user says things like:

- "set up baseline metrics"
- "do analytics onboarding"
- "connect Search Console and Umami"
- "the final domain is live; add indexing"

## Preconditions

These are the only hard preconditions for the whole skill:

1. the site is already deployed
2. the final custom domain is decided
3. the final custom domain is publicly reachable
4. redirect policy is already settled, for example `www -> apex`

If the site is only live on a platform URL or the custom domain is still propagating, stop and use `new-domain-launch` first.

Do not stop the whole workflow because one optional integration lacks credentials. Continue with the other integrations and report the skipped or blocked step at the end.

## Inputs

- Required: final public domain, for example `example.com`
- Optional: repo override if the site-to-repo mapping is missing
- Optional: integration config path; default to `$SITE_INTEGRATIONS_CONFIG` if set

## Goal

Attempt the basic public-site onboarding on the final domain:

- analytics script is wired and live, or skipped with reason
- Search Console ownership is verified, or skipped/blocked with reason
- `robots.txt` and `sitemap.xml` are live if the repo can be edited and deployed
- sitemap is submitted where credentials allow it
- IndexNow is installed or confirmed already present for the final domain
- Bing Webmaster Tools has the site added and verified, or skipped/blocked with reason
- Clarity is verified from the shared integration map, or skipped with reason

## Core Rules

- Always use the final custom domain, not the temporary platform URL, as the source of truth.
- Do not onboard Search Console before the final domain is stable.
- Do not generate or publish an IndexNow key until the final domain is settled.
- Do not pretend verification is complete if the homepage is live but `sitemap.xml` is missing.
- Do not assume IndexNow automatically registers the site in Bing Webmaster Tools.
- Read-only metrics/reporting tools should not be used to provision these integrations.
- Missing credentials block only the integration that needs those credentials.
- If one integration cannot run, record `skipped` or `blocked` and continue with the next integration.
- If a code change is needed but the repo cannot be resolved, skip repo-editing steps and continue with API-only or live-site checks.
- If a deploy is needed but deployment credentials are missing, keep the local change unclaimed as live and continue with checks that do not need deployment.
- Clarity project id and token are project-scoped. Read them only from the shared integration map. Do not ask for them interactively and do not read global Clarity env vars.

## Status Terms

Use these status terms in the final report:

- `done`: completed and verified
- `partial`: some substeps completed, but verification or deployment is incomplete
- `skipped`: not attempted because required inputs or credentials were absent
- `blocked`: attempted but could not finish because of an external error, permission issue, or unresolved dependency
- `manual`: needs user action outside the current automation path

## Repo Resolution

Prefer reading the project integration map if the user has one. If `$SITE_INTEGRATIONS_CONFIG` is set, read that file:

```bash
cat "$SITE_INTEGRATIONS_CONFIG"
```

If `$SITE_INTEGRATIONS_CONFIG` is unset, empty, missing on disk, or cannot be parsed, do not block the workflow. Continue with repo resolution from the current directory or explicit repo override, skip integrations that require the map, and report the missing map in the final summary.

Expected shape:

```json
{
  "domains": {
    "example.com": {
      "repo_dir": "/absolute/path/to/repo",
      "clarity": {
        "project_id": "existing-clarity-project-id",
        "project_name": "Optional project name",
        "token": "project-level-data-export-token"
      }
    }
  }
}
```

If the user does not maintain a shared map, resolve the repo from the current directory or an explicit repo override.
Treat the `clarity` object as optional. If the map or the target domain's `clarity` object is missing, skip Clarity and continue.

## Workflow

### 1. Confirm the live domain really is the final one

Verify:

- the canonical host is known
- the live domain returns the site successfully
- any `www` redirect policy is already in place

If the domain is still in transition, stop here and hand back to `new-domain-launch`. The rest of this skill depends on the final domain being live.

### 2. Analytics onboarding

Prefer the analytics provider the user already uses. If the user has not chosen one and Umami credentials are available, use Umami.

If analytics credentials are missing:

1. Check whether the live site already has an analytics script.
2. If it is already installed, report `done` or `partial` based on what can be verified.
3. If it is not installed, report analytics as `skipped` and continue to Search Console.

For Umami specifically:

- do not hardcode a specific Umami server URL in this skill; read the API base URL from `UMAMI_BASE_URL`, for example an origin plus `/api`
- for self-hosted Umami, authenticate by posting `UMAMI_ADMIN_USERNAME` and `UMAMI_ADMIN_PASSWORD` to `<UMAMI_BASE_URL>/auth/login`, then use `Authorization: Bearer <token>`
- for self-hosted Umami, list visible websites with `GET <UMAMI_BASE_URL>/me/websites`; if the account is an admin and site creation or full lookup is needed, use the documented admin endpoints such as `GET <UMAMI_BASE_URL>/admin/websites`
- `UMAMI_API_KEY` is for Umami Cloud or compatible providers that explicitly support API-key auth; do not require it for self-hosted Umami
- if neither a Cloud API key nor self-hosted login credentials are available, skip Umami and continue
- if the base URL or the target website id cannot be resolved or created, skip Umami and continue
- do not block Search Console, `robots.txt`, `sitemap.xml`, IndexNow, Bing Webmaster Tools, or Clarity because Umami cannot be provisioned
- if only a script URL is available without a website id, do not inject an incomplete script

Self-hosted Umami login pattern:

```bash
TOKEN=$(curl -sS "$UMAMI_BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  --data "{\"username\":\"$UMAMI_ADMIN_USERNAME\",\"password\":\"$UMAMI_ADMIN_PASSWORD\"}" \
  | jq -r '.token')

curl -sS "$UMAMI_BASE_URL/me/websites" \
  -H "Authorization: Bearer $TOKEN"
```

Minimum goal:

- ensure the analytics site/project exists for the root domain
- wire the correct analytics script into the repo
- deploy the repo if code changed
- verify the live HTML on the final domain loads the expected script URL and site/project id

If the repo is a static site, inject the script directly into the HTML entry point.

If the repo is env-driven, wire:

- `NEXT_PUBLIC_UMAMI_WEBSITE_ID`
- `NEXT_PUBLIC_UMAMI_SCRIPT` or the repo's existing analytics env names

### 3. Search Console onboarding

Use the final domain as the property source of truth.

If Google credentials are missing:

1. Still check whether `robots.txt` and `sitemap.xml` are live.
2. If the repo can be resolved, add or fix `robots.txt` and `sitemap.xml` if needed.
3. Report Search Console ownership and sitemap submission as `skipped`.
4. Continue to IndexNow.

Recommended flow:

1. Check whether `sc-domain:<domain>` already exists.
2. If missing, call Google Site Verification API `getToken` with `DNS_TXT`.
3. Add the TXT token in DNS.
4. Call Site Verification API `insert` to verify ownership.
5. Call Search Console API `sites.add` for `sc-domain:<domain>`.
6. Ensure the live site exposes:
   - `robots.txt`
   - `sitemap.xml`
7. Submit the sitemap with Search Console API.

Important:

- verification alone is not enough
- if the homepage is `200` but `sitemap.xml` is `404`, treat onboarding as partial

### 4. IndexNow onboarding

Treat IndexNow as part of post-domain indexing setup, not core deployment.

Preferred handling:

1. Check whether the repo already has an IndexNow implementation.
2. If it does not, use the bundled `add-indexnow` skill from this skill pack rather than rebuilding the workflow here.
3. Generate a fresh host-scoped key only for the final domain.
4. Ensure the verification file is served on the final domain.
5. Ensure the repo has a clear collect-and-submit path for URL submission.
6. Validate against the real final host, not the temporary deployment URL.

Minimum goal:

- key file is present and publicly reachable on the final host
- repo has a reusable submission workflow
- IndexNow setup matches the final canonical domain

Important:

- if the site moved from a temporary host to a final domain, do not reuse a key tied to the wrong host
- if an IndexNow implementation already exists, update it instead of duplicating scripts
- prefer reusing `add-indexnow` as the implementation skill and keep `index-onboarding` as the orchestrator

If the repo cannot be resolved or edited, report IndexNow as `skipped` and continue to Bing Webmaster Tools.

### 5. Bing Webmaster Tools onboarding

Treat Bing Webmaster Tools as separate from IndexNow.

Important:

- IndexNow URL submission does not by itself make the site appear in Bing Webmaster Tools
- if `BING_WEBMASTER_API_KEY` is available, prefer the API route over manual browser import
- importing from Google Search Console is still valid, but it is optional rather than required

If Bing credentials and browser access are missing, report Bing Webmaster Tools as `skipped` and continue to Clarity.

Preferred API flow:

1. Check `GetUserSites` to see whether the final domain is already present.
2. If missing, call `AddSite` for the final canonical URL, for example `https://example.com/`.
3. Read the returned site metadata from `GetUserSites`, especially:
   - `AuthenticationCode`
   - `DnsVerificationCode`
   - `IsVerified`
4. Prefer HTML meta verification for static or repo-controlled sites:
   - add `<meta name="msvalidate.01" content="<AuthenticationCode>" />` to the live homepage head
   - deploy the repo if code changed
5. Once the verification token is live on the final host, call `VerifySite`.
6. Recheck `GetUserSites` until the site appears with `IsVerified = true`, or report a refresh delay if `VerifySite` succeeded but site state has not caught up yet.
7. Submit the sitemap through the Bing Webmaster API `SubmitFeed`.
8. Optionally submit the homepage or changed URLs through `SubmitUrl` as an additional discovery push.

Alternative path:

- if the user explicitly prefers Bing's "Import from Google Search Console" flow and browser access is available, use that route instead of API add-and-verify

Minimum goal:

- the site appears in Bing Webmaster Tools for the owning account
- verification state is known
- sitemap submission state is known

Validation notes:

- `VerifySite` may return success before `GetUserSites` reflects `IsVerified = true`
- treat that as a short-lived consistency delay, not an automatic failure
- verify against the final canonical URL with trailing slash consistency

### 6. Clarity onboarding

Clarity is project-scoped. The only supported credential source is the shared integration map configured by `$SITE_INTEGRATIONS_CONFIG`.

Microsoft's Clarity MCP server and Data Export API require an existing Clarity project and a project-level Data Export API token. Treat them as analytics read/query tools, not as project-creation APIs.

Do not request Clarity credentials interactively. Do not use global env vars such as `CLARITY_PROJECT_ID` or `CLARITY_API_TOKEN`.

Preferred handling:

1. Resolve the target domain in the integration map.
2. Read `domains[hostname].clarity`.
3. If `clarity.project_id` and `clarity.token` are present, verify the live site has the matching Clarity script and query the Data Export API where needed.
4. If `$SITE_INTEGRATIONS_CONFIG` is missing, unreadable, or invalid, report Clarity as `skipped` with the reason `no site-integrations config`.
5. If the `clarity` object, project id, or token is missing, report Clarity as `skipped` with the reason `no site-integrations clarity config`.
6. If the Clarity script is installed but the integration map lacks a token, report `partial` only if the live script is verifiable; otherwise report `skipped`.

Do not mark Clarity complete unless the real project wiring is verifiable.

### 7. Update shared integration metadata

When new onboarding is completed, update the integration metadata repo as needed:

- the integration map configured by `$SITE_INTEGRATIONS_CONFIG`
- provider cache files if the user's workflow depends on them

If `$SITE_INTEGRATIONS_CONFIG` is unavailable, skip metadata-map updates and report that no integration map was updated.

Keep these updates narrowly scoped to the target domain.

## Validation checklist

Do not consider an individual integration complete until its relevant checks pass. The whole workflow can still finish with skipped or blocked integrations.

1. the final custom domain is the one being checked
2. live HTML on the final domain includes the expected analytics script and site/project id
3. Search Console ownership is verified, skipped, or clearly blocked with reason
4. `robots.txt` exists on the final domain
5. `sitemap.xml` exists on the final domain
6. sitemap submission state is known
7. IndexNow key file and submission workflow state are known
8. Bing Webmaster Tools site state is known
9. Clarity is verified from site integrations or skipped because the target domain lacks Clarity config

## Reporting

Summarize in this order. Every integration should have a status term and a reason when not `done`:

1. final domain used
2. repo resolved
3. analytics status
4. Search Console ownership status
5. `robots.txt` and `sitemap.xml` status
6. sitemap submission status
7. IndexNow status
8. Bing Webmaster Tools status
9. Clarity status
10. remaining blockers, if any

## Boundary

- `upstart-site` owns repo-to-hosted-deploy release
- `new-domain-launch` owns registrar / DNS / domain cutover
- `index-onboarding` owns post-domain-launch analytics and indexing setup
- `add-indexnow` is the reusable implementation skill for IndexNow file/script generation
- read-only metrics/reporting skills only read from already-onboarded systems
