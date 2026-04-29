---
name: index-onboarding
version: "1.1.0"
description: "Use after a public site is live on its final custom domain and the user asks for analytics, baseline metrics, Search Console, sitemap submission, IndexNow, Bing Webmaster Tools, or Clarity setup. Trigger on requests like 'set up GSC', 'connect analytics', 'do indexing onboarding', or '域名好了，接搜索和统计'. Do not use for initial deployment or DNS cutover; use upstart-site or new-domain-launch first."
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

## Preconditions

These are the only hard preconditions for the whole skill:

1. the site is already deployed
2. the final custom domain is decided
3. the final custom domain is publicly reachable

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
- Clarity is verified from the shared integration map or `CLARITY_ID` / `CLARITY_TOKEN`, or skipped with reason

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
- Clarity project id and token are project-scoped. Prefer the shared integration map, then fall back to `CLARITY_ID` and `CLARITY_TOKEN` from the current process or the resolved repo's local dotenv files. Do not ask for them interactively.

## Status Terms

See repo-root `docs/status-terms.md` for the full definitions and usage rules shared across all skills in this pack.

## Repo Resolution

Prefer reading the project integration map if the user has one. If `$SITE_INTEGRATIONS_CONFIG` is set, read that file:

```bash
cat "$SITE_INTEGRATIONS_CONFIG"
```

If `$SITE_INTEGRATIONS_CONFIG` is unset, empty, missing on disk, or cannot be parsed, do not block the workflow. Continue with repo resolution from the current directory or explicit repo override, skip integrations that require the map, and report the missing map in the final summary.

Expected shape: `assets/site-integrations.schema.json`.

If the user does not maintain a shared map, resolve the repo from the current directory or an explicit repo override.
Treat the `clarity` object as optional. If the map or the target domain's `clarity` object is missing, try `CLARITY_ID` and `CLARITY_TOKEN` from the current environment, then from the resolved repo's `.env` and `.env.local`, before skipping Clarity.

To configure the map for a domain:

1. Create or update a local JSON file such as `config/site-integrations.json`.
2. Add `domains[hostname].repo_dir` if repo resolution should come from the map.
3. Add `domains[hostname].clarity.project_id` and `domains[hostname].clarity.token` only after the Clarity project and project-level Data Export API token already exist.
4. Point `SITE_INTEGRATIONS_CONFIG` at that file before running this skill.

```bash
export SITE_INTEGRATIONS_CONFIG=/absolute/path/to/config/site-integrations.json
```

Keep the map out of public commits if it contains project tokens.

If there is no map entry for the target domain, read Clarity credentials from the current environment or from the resolved repo's local dotenv files:

```bash
export CLARITY_ID=existing-clarity-project-id
export CLARITY_TOKEN=project-level-data-export-token
```

Credential presence check:

```bash
test -n "${CLARITY_ID:-}" && test -n "${CLARITY_TOKEN:-}"
```

When checking repo-local dotenv files, do not print secret values. Report only `set` / `empty` and value lengths.

Use environment credentials only for the current run. Do not write them back to the integration map unless the user asks.

## Workflow

### 1. Confirm the live domain really is the final one

Verify:

- the canonical host is known
- the live domain returns the site successfully
- any `www` redirect policy is already in place

If the domain is still in transition, stop here and hand back to `new-domain-launch`. The rest of this skill depends on the final domain being live.

### 2. Analytics onboarding

Prefer the analytics provider the user already uses. If the user has not chosen one and Umami credentials are available, use Umami.

For Umami, prefer self-hosted admin login. Use Umami Cloud API-key auth only when self-hosted admin credentials are unavailable.

If analytics credentials are missing:

1. Check whether the live site already has an analytics script.
2. If it is already installed, report `done` or `partial` based on what can be verified.
3. If it is not installed, report analytics as `skipped` and continue to Search Console.

For Umami, read `references/umami.md`.

### 3. Search Console onboarding

Read `references/search-console.md`.

### 4. IndexNow onboarding

Read `references/indexnow.md`.

### 5. Bing Webmaster Tools onboarding

Read `references/bing-webmaster.md`.

### 6. Clarity onboarding

Read `references/clarity.md`.

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
9. Clarity is verified from the integration map or `CLARITY_ID` / `CLARITY_TOKEN`, or skipped because both sources lack complete credentials

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
