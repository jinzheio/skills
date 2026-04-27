---
name: upstart-site
description: "Bootstrap and publish a local site repo end to end: create or connect a GitHub repo, review and commit the intended local changes, push safely, connect the repo to a Vercel project under the requested team, sync minimum production env vars, and release via GitHub-triggered deployment. Use when the user wants to take a local website or app repo from local-only to a stable hosted deployment."
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
10. if requested and the final domain already lives on Cloudflare, enable basic inbound email forwarding

Do not treat "vercel --prod" from the local checkout as completion unless the user explicitly asks for local-source deployment. Default to GitHub-connected deploys.

If the user also wants a real public domain and search / analytics onboarding, the intended follow-up sequence is:

1. `new-domain-launch`
2. `index-onboarding`

If the user also wants inbound email forwarding on the final domain, that can be handled after the domain is on Cloudflare. It is optional and should not block the core repo-to-hosted-deploy release path.

## Best Fit

Use this when the user says things like:

- "publish this local website"
- "create a GitHub repository and deploy it"
- "connect this project to Vercel"
- "push this project and make it reachable"
- "launch this local app end to end"

This skill is especially appropriate for Next.js and other static or server-rendered web repos.

## Inputs

- Required: local repo path, or run from inside the target repo
- Required: GitHub owner to use, for example `acme`
- Required: Vercel team or scope, for example `acme-team`
- Optional: desired repo or project name; default to the local directory name
- Optional: monorepo app root, for example `apps/web`
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
- Do not attempt Cloudflare Email Routing before the final domain is already delegated to Cloudflare and publicly stable.

## Workflow

### 1. Inspect local repo state

Run:

```bash
pwd
git status --short --branch
git remote -v
git branch --show-current
rg --files -g 'package.json' -g 'pnpm-lock.yaml' -g 'package-lock.json' -g 'yarn.lock' -g 'bun.lockb' -g 'bun.lock'
```

Then inspect likely app entry points and build scripts:

```bash
sed -n '1,220p' package.json
find . -maxdepth 3 \( -name 'package.json' -o -name 'next.config.*' -o -name 'vercel.json' -o -name 'pnpm-workspace.yaml' \)
```

Determine:

- whether this is already a git repo
- whether a remote already exists
- whether the repo is clean or mixed
- whether this is a single app or a monorepo
- which directory should be deployed on Vercel

For monorepos, identify the deploy root before linking Vercel. Common examples:

- `apps/web`
- `app`
- `frontend`

### 2. Verify local build before release

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

### 3. Create or connect the GitHub repo

If no usable remote exists, create a private repo under the requested owner:

```bash
gh repo create <owner>/<repo-name> --private --source=. --remote=origin --push
```

If the user explicitly wants a public repository, replace `--private` with `--public`.

Before creating, check whether the repo already exists:

```bash
gh repo view <owner>/<repo-name> --json nameWithOwner,visibility,defaultBranchRef
```

If it exists already:

- do not recreate it
- point `origin` to that repo if needed

After creation or connection, verify:

```bash
git remote -v
gh repo view <owner>/<repo-name> --json nameWithOwner,url,defaultBranchRef
```

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

### 6. Create or link the Vercel project

Use the requested team or scope.

Check for an existing linked project:

```bash
cat .vercel/project.json
vercel project inspect <project-name> --scope <team>
```

If the project does not exist, create it:

```bash
vercel project add <project-name> --scope <team>
vercel link --project <project-name> --scope <team> --yes
```

### 7. Force GitHub integration, not local-source deploy

Connect the Vercel project to the GitHub repo:

```bash
vercel git connect git@github.com:<owner>/<repo-name>.git --scope <team> --yes
```

If SSH is unavailable but HTTPS is the actual remote, use the HTTPS GitHub URL instead.

After connecting, confirm the deployment metadata later shows GitHub commit fields such as:

- `githubCommitSha`
- `githubCommitRef`
- `githubRepo`

If those are absent, the release did not go through the intended GitHub path.

### 8. Set monorepo root and framework correctly

If this is not a single-app repo rooted at `.`, explicitly configure the Vercel project root.

Preferred API-style update:

```bash
TOKEN=$(jq -r .token "$HOME/Library/Application Support/com.vercel.cli/auth.json")
curl -sS -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.vercel.com/v9/projects/${PROJECT_ID}?teamId=${TEAM_ID}" \
  -d '{"rootDirectory":"<app-root>","framework":"nextjs"}'
```

At minimum, confirm afterward that:

- `Root Directory` matches the intended app directory
- framework is correct, for example `Next.js`

### 9. Sync minimum production env vars

Do not blindly upload every local env var.

Start from:

- `.env.production` if present
- otherwise `.env`
- otherwise `.env.example` only as a key reference, not as a source of secrets

Sync only the variables required for production build and runtime of the deployed app.

Typical examples:

- `NEXT_PUBLIC_APP_URL`
- auth secrets and callback URLs
- database connection string
- analytics public keys
- third-party OAuth credentials

Use:

```bash
printf '%s' '<value>' | vercel env add <KEY> production --scope <team> --yes --force
```

Before first deploy, check:

```bash
vercel env ls production --scope <team>
```

If the build requires values that are still missing, stop and report the exact keys.

### 10. Optional: enable Cloudflare Email Routing catch-all forwarding

Only do this when the user explicitly asks for domain email forwarding and the final domain is already on Cloudflare.

Preconditions:

- the final custom domain is already delegated to Cloudflare
- the zone is active
- the user has provided or already configured the forwarding destination
- Cloudflare token or browser session has permission for Email Routing

Preferred flow:

1. Check Email Routing status for the zone.
2. If Email Routing is disabled, enable it and let Cloudflare add the required MX, SPF, and DKIM records.
3. Check whether the destination mailbox already exists as a verified Email Routing address.
4. If not verified, create the destination address and complete its mailbox verification.
5. Update the catch-all rule from the default `drop` action to `forward`.
6. Verify the catch-all rule points to the intended destination.
7. Optionally send a real test email through an existing sender such as Mailgun to confirm end-to-end forwarding.

Important:

- this is for inbound forwarding such as `*@example.com -> destination@example.net`
- Email Routing requires Cloudflare-managed DNS for the final domain
- do not claim success if the zone still shows Email Routing as `unconfigured`
- if API token scope is insufficient, fall back to browser automation or report the exact missing permission

Minimum goal:

- Email Routing is `enabled`
- MX records point to Cloudflare mail exchangers
- required SPF and DKIM records exist
- catch-all rule is enabled and forwards to the intended mailbox
- test send status is known if a sender is available

### 10. Trigger a GitHub-based production deploy

If the repo was just connected to Vercel after the latest push, create a follow-up commit or empty commit so GitHub emits a new deployment event:

```bash
git commit --allow-empty -m "chore: trigger vercel deployment"
git push origin $(git branch --show-current)
```

Then inspect deployments:

```bash
vercel list <project-name> --scope <team>
vercel inspect <deployment-url> --scope <team>
vercel inspect <deployment-url> --scope <team> --logs
```

If the deployment fails, treat that as part of the release workflow:

1. read logs
2. fix the blocker locally
3. validate locally
4. commit and push the fix
5. verify the next GitHub-triggered deployment

Common first-deploy failure:

- `ERR_PNPM_OUTDATED_LOCKFILE`

If you see that, run local install to resync the lockfile, commit it, and push again.

### 11. Verify success

A release is complete only when all of these are true:

1. the code is on GitHub
2. the Vercel project is connected to that GitHub repo
3. the deployment used GitHub metadata
4. the latest production deployment is `Ready`
5. you have a working production URL

Preferred checks:

```bash
vercel list <project-name> --scope <team>
vercel inspect <deployment-url> --scope <team>
curl -I "https://${PRODUCTION_HOSTNAME}"
```

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
