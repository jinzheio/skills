---
name: upstart-site
version: "1.1.0"
description: "Use when the user wants to publish a local website or web app end to end, including 'deploy this site', 'publish this local app', 'create a GitHub repo and deploy to Vercel', or '上线到 Vercel'. Create or connect GitHub, validate build, push, link Vercel, sync minimum production env vars, and verify a GitHub-triggered deployment. Do not handle custom-domain cutover or search/analytics onboarding except as follow-up handoff."
---

# Upstart Site

Use this skill for the full "local repo to live site" flow.

This is a release workflow, not just a deploy command. The job is to make the repo publishable and connected correctly:

1. inspect the local repo and build status
2. create or connect a GitHub repo
3. fix blockers that would prevent CI or Vercel from building
4. commit and push intentionally
5. create or link a Vercel project under the requested team
6. connect Vercel to GitHub
7. configure the correct app root for monorepos
8. sync the minimum required production env vars
9. trigger and verify a GitHub-based production deployment

Do not treat "vercel --prod" from the local checkout as completion unless the user explicitly asks for local-source deployment. Default to GitHub-connected deploys.

If the user also wants a real public domain and search / analytics onboarding, the intended follow-up sequence is:

1. `new-domain-launch`
2. `index-onboarding`

If the user also wants inbound email forwarding on the final domain, hand that off to `new-domain-launch` after the domain is on Cloudflare. It is optional and should not block the core repo-to-hosted-deploy release path.

## Inputs

- Required: local repo path, or run from inside the target repo
- Required: GitHub owner to use, for example `jinzheio`
- Required: Vercel team or scope, for example `my-team`
- Optional: desired repo or project name; default to the local directory name
- Optional: monorepo app root, for example `app`
- Optional: whether production env vars should be copied from `.env.production`, `.env`, or another source
- Optional: repo visibility; default to private unless the user asks for public

If the user does not specify repo name or Vercel project name, default to the current directory name.

## Required Tools and Auth

Before doing any repo or deploy changes, confirm these are available:

- `gh --version`
- `gh auth status`
- `vercel --version`
- `vercel whoami`

If `gh` or `vercel` is missing, stop and say exactly which CLI is missing.
If auth is missing, stop and ask the user to authenticate first.

## Core Rules

- Prefer `rg` for repo inspection.
- Never use `git add .`.
- Never push unrelated local changes silently.
- Never use destructive git commands like `reset --hard`.
- Default to a private GitHub repo unless the user asks for public.
- Default to GitHub-triggered Vercel deploys.
- If the repo is a monorepo, explicitly set the Vercel root directory.
- If the lockfile is stale, fix it before shipping.
- If local build fails, fix or surface the blocker before attempting release.
- Do not mix domain cutover or indexing work into the core repo-to-hosted-deploy release path.

## Workflow

### 1. Plan

Read `references/github-vercel-release.md` and run the Repo Inspection commands there. Then produce a plan covering:

- target GitHub owner and repo name
- repo visibility
- current branch and dirty-worktree state
- package manager and build/check commands
- Vercel team/scope and project name
- deploy root (especially for monorepos)
- production env keys to sync, without values
- expected production URL
- follow-up handoff, if a custom domain or indexing is requested

Ask for user confirmation before creating GitHub repos, linking Vercel projects, pushing, or writing production env vars unless the user already explicitly authorized the full publish flow.

### 2. Validate Local Release Path

Find the most relevant checks and run them before any publish action.

Typical order:

```bash
pnpm install
pnpm build
```

Fallbacks:

- `npm install && npm run build`
- `yarn install && yarn build`
- repo-specific lint or typecheck commands if build is absent

If the build fails:

1. identify the real blocker
2. fix it if the change is low-risk and directly necessary for release
3. rerun the validation

Common blockers to catch:

- stale lockfile
- missing Next.js experimental flag required by current code
- missing monorepo root configuration
- missing required env parsing defaults during build

Do not proceed to shipping while the release path is still broken.

### 3. Create Or Connect GitHub

Use `references/github-vercel-release.md`. Default to a private repo unless the user asks for public.

### 4. Commit intentionally

If local changes are part of the release, review and commit them deliberately.

Prefer using the existing `commit-code` skill when available. If it is not available, follow the same intent manually:

1. inspect `git diff`
2. stage only intended files
3. commit with a concise message

Never batch unrelated work into the release commit.

### 5. Push safely

Prefer using the existing `push-code` skill when available. If it is not available, push manually:

```bash
git push -u origin $(git branch --show-current)
```

If push is rejected because remote moved ahead:

```bash
git pull --rebase --autostash origin $(git branch --show-current)
git push -u origin $(git branch --show-current)
```

### 6. Create Or Link Vercel

Use `references/github-vercel-release.md`. Force GitHub integration rather than local-source deployment.

### 7. Sync Minimum Production Env Vars

Use `references/env-sync.md` only when production env vars are needed. Report key names only, never values.

### 8. Trigger And Verify Production Deploy

Use `references/deploy-verify.md`. The release is complete only when the latest production deployment is `Ready`, includes GitHub metadata, and the production URL responds.

## Reporting

Summarize the result in this order:

1. GitHub repo created or connected
2. commits pushed
3. Vercel project and scope
4. root directory and framework used
5. production env vars synced, described by key names only
6. final production URL
7. whether custom-domain handoff is still needed
8. any remaining operational risk

## Do Not Skip

- build validation
- lockfile health
- private repo creation
- Vercel GitHub connection
- root directory configuration for monorepos
- production env sanity
- final deploy verification

This skill is successful only when the repo is truly publishable and the site is actually live.

For custom-domain public launch follow-up, hand off to:

- `new-domain-launch` for registrar / DNS / hosting cutover
- `index-onboarding` for Umami, Search Console, IndexNow, Bing Webmaster Tools, and Clarity onboarding on the final domain
