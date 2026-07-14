# skills

English | [中文](README.zh.md)

Reusable agent skills for one-person company work. `ship/` contains site-building, launch, growth, and site-operations skills. Other subdirectories group topics such as content production and infrastructure operations.

This repository is a public skill pack. Each skill folder contains its own `SKILL.md` and optional bundled resources.

Skill names follow the [`jz-<method>-<resource>[-<qualifier>]` convention](docs/skill-naming.md).

## Ship Skills

| Skill | Use it for |
| --- | --- |
| `jz-deploy-vercel` | Publish a local web project through GitHub and Vercel. |
| `jz-launch-cloudflare-site` | Orchestrate a new site from local code to Cloudflare deploy, domain, analytics, and optional Auto PR. |
| `jz-deploy-cloudflare` | Publish a local web project to Cloudflare Workers. |
| `jz-migrate-vercel-to-cloudflare` | Move a web project from Vercel to Cloudflare. |
| `jz-setup-site-domain` | Connect a deployed site to a custom domain with DNS, HTTPS, and redirects. |
| `jz-setup-site-analytics` | Set up analytics and search indexing after the final domain works. |
| `jz-setup-indexnow` | Add IndexNow key verification, URL collection, and submission scripts to an existing site. |
| `jz-setup-conversion-tracking` | Design and implement conversion funnel event tracking. |
| `jz-get-site-metrics` | Check live site metrics across GSC, Cloudflare, Umami, and Clarity. |
| `jz-check-site-speed` | Check PageSpeed, CrUX, and Cloudflare RUM data. |
| `jz-setup-github-agent-access` | Prepare fork-only GitHub permissions for a cloud-agent developer account. |
| `jz-commit-code` | Review workspace changes and create scoped commits after confirmation. |
| `jz-push-code` | Verify, push, and run post-push indexing sync. |
| `jz-setup-testing` | Set up or improve test infrastructure — vitest, coverage, CI, E2E. Supports Next.js, Astro, TanStack Start. |
| `jz-create-test-plan` | Turn a feature idea, spec, issue, conversation, or branch diff into a gstack QA-ready test plan. |
| `jz-check-vercel-cost` | Explain Vercel usage, billed cost, Pro fees, and receipt/card charge differences. |
| `jz-check-cloudflare-cost` | Read Cloudflare bills and GraphQL usage, check running resource costs in the current billing cycle, and identify billing anomalies. |
| `jz-check-neon-usage` | Find why a Neon database is receiving requests or cannot scale to zero. |
| `jz-create-cloudflare-token` | Create or update a minimal Cloudflare token for a project. |
| `jz-setup-mailgun-domain` | Initialize a Mailgun sending domain, Cloudflare DNS, and a domain-scoped sending key. |
| `jz-setup-auto-pr` | Connect a GitHub repo to the local Auto PR self-hosted runner for Codex or Claude Code. |
| `jz-setup-tailwind-theme` | Initialize or adjust Tailwind v4 theme tokens. |
| `jz-get-revenue-sites` | Find high-revenue sites similar to a given domain or product category. |
| `jz-check-market-demand` | Validate whether a product idea has search demand, paid competitors, and a reachable buyer path. |
| `jz-make-viral` | 32 viral product principles + 5 landing page design laws, topic-routed: landing page design, copywriting, pricing, product positioning, visual branding. |
| `jz-manage-cloud-agent` | Diagnose and operate cloud agent deployments, and sync skills to Hermes/OpenClaw. |

## Other Topics

| Path | Topic | Skills |
| --- | --- | --- |
| `ship/` | Site-building, launch, growth, and site operations | See "Ship Skills" above. |
| `content/` | Content production and distribution | `jz-get-x-posts`, `jz-get-feishu-doc`, `jz-get-scys-article`, `jz-get-video-transcript`, `jz-transcribe-media`, `jz-get-douyin-transcripts`, `jz-sync-wechat-archive`, `jz-get-readest-highlights`, `jz-create-marketing-video`, `jz-create-book-notes`, `jz-edit-talking-head-video` |
| `infra/` | Infrastructure operations | `jz-send-notification`, `jz-manage-cron-jobs`, `jz-manage-litellm`, `jz-manage-cloudflare-ai-gateway`, `jz-manage-newapi`, `jz-manage-ovh-servers`, `jz-manage-hetzner-servers` |
| `local/` | Local machine operations | `jz-setup-browser-automation`, `jz-launch-chrome`, `jz-manage-launchd-tasks`, `jz-connect-mac`, `jz-review-bug`, `jz-setup-personal-context` |

Recommended sequence for a new site:

```text
jz-launch-cloudflare-site
```

For a manual Cloudflare path, use `jz-deploy-cloudflare -> jz-setup-site-domain -> jz-setup-site-analytics`.
`jz-setup-indexnow` is separate because it is also useful for existing sites that only need IndexNow support.

## Code Upload Workflow

For normal development work, use:

```text
jz-commit-code -> jz-push-code
```

`jz-commit-code` reviews the working tree, reports risks, waits for confirmation, and commits only the intended files. `jz-push-code` runs verification, keeps the git tree clean, pushes the branch, and then uses `jz-setup-indexnow` to ensure IndexNow URL collection and submission are available for changed public pages.

`jz-push-code` should not resubmit an unchanged sitemap to Google Search Console after every page edit. It should check or submit a sitemap only when the sitemap route, robots reference, canonical host, public route structure, or Search Console state changed. For ordinary edits to existing pages, IndexNow URL submission is the post-push sync path.

## Install

Clone the repository:

```bash
git clone https://github.com/<owner>/<repo>.git
```

Then copy or symlink the skills you want into the skills directory supported by your agent or runner.

The `ship/` directory is the development and site-building set: publishing, domains, analytics, search indexing, code review, billing, and related product/site work. Other subdirectories are other one-person company topics. For example, `content/` contains content production and distribution skills, and `infra/` contains infrastructure operations skills. All of them are valid skills and follow the same `SKILL.md` convention; the directory only tells you the topic.

Codex example:

```bash
mkdir -p ~/.codex/skills
cp -R ship/jz-deploy-vercel ~/.codex/skills/
cp -R ship/jz-launch-cloudflare-site ~/.codex/skills/
cp -R ship/jz-deploy-cloudflare ~/.codex/skills/
cp -R ship/jz-migrate-vercel-to-cloudflare ~/.codex/skills/
cp -R ship/jz-setup-site-domain ~/.codex/skills/
cp -R ship/jz-setup-site-analytics ~/.codex/skills/
cp -R ship/jz-setup-indexnow ~/.codex/skills/
cp -R ship/jz-setup-conversion-tracking ~/.codex/skills/
cp -R ship/jz-get-site-metrics ~/.codex/skills/
cp -R ship/jz-check-site-speed ~/.codex/skills/
cp -R ship/jz-setup-github-agent-access ~/.codex/skills/
cp -R ship/jz-commit-code ~/.codex/skills/
cp -R ship/jz-push-code ~/.codex/skills/
cp -R ship/jz-check-vercel-cost ~/.codex/skills/
cp -R ship/jz-check-cloudflare-cost ~/.codex/skills/
cp -R ship/jz-check-neon-usage ~/.codex/skills/
cp -R ship/jz-create-cloudflare-token ~/.codex/skills/
cp -R ship/jz-setup-mailgun-domain ~/.codex/skills/
cp -R ship/jz-setup-auto-pr ~/.codex/skills/
cp -R ship/jz-setup-tailwind-theme ~/.codex/skills/
cp -R ship/jz-get-revenue-sites ~/.codex/skills/
cp -R ship/jz-check-market-demand ~/.codex/skills/
cp -R ship/jz-make-viral ~/.codex/skills/
cp -R ship/jz-manage-cloud-agent ~/.codex/skills/
cp -R ship/jz-setup-testing ~/.codex/skills/
cp -R ship/jz-create-test-plan ~/.codex/skills/
cp -R content/jz-get-x-posts ~/.codex/skills/
cp -R content/jz-get-feishu-doc ~/.codex/skills/
cp -R content/jz-get-scys-article ~/.codex/skills/
cp -R content/jz-get-video-transcript ~/.codex/skills/
cp -R content/jz-transcribe-media ~/.codex/skills/
cp -R content/jz-get-douyin-transcripts ~/.codex/skills/
cp -R content/jz-sync-wechat-archive ~/.codex/skills/
cp -R content/jz-get-readest-highlights ~/.codex/skills/
cp -R content/jz-create-marketing-video ~/.codex/skills/
cp -R content/jz-create-book-notes ~/.codex/skills/
cp -R content/jz-edit-talking-head-video ~/.codex/skills/
cp -R infra/jz-manage-cron-jobs ~/.codex/skills/
cp -R infra/jz-manage-litellm ~/.codex/skills/
cp -R infra/jz-send-notification ~/.codex/skills/
cp -R infra/jz-manage-cloudflare-ai-gateway ~/.codex/skills/
cp -R infra/jz-manage-newapi ~/.codex/skills/
cp -R infra/jz-manage-ovh-servers ~/.codex/skills/
cp -R infra/jz-manage-hetzner-servers ~/.codex/skills/
cp -R local/jz-setup-browser-automation ~/.codex/skills/
cp -R local/jz-launch-chrome ~/.codex/skills/
cp -R local/jz-manage-launchd-tasks ~/.codex/skills/
cp -R local/jz-connect-mac ~/.codex/skills/
cp -R local/jz-review-bug ~/.codex/skills/
cp -R local/jz-setup-personal-context ~/.codex/skills/
```

If your runner can read this repository directly, no copy step is needed.

Each skill may include an `agents/openai.yaml` file. These files provide display metadata and default prompts for OpenAI/Codex-style runners. The skills still work from `SKILL.md` without that metadata, but the metadata is useful when publishing or listing the pack.

## Usage

Invoke a skill by name in your agent:

```text
Use $jz-launch-cloudflare-site to publish this new site to Cloudflare, then set up the domain, analytics, and Auto PR if needed.
```

```text
Use $jz-deploy-vercel to publish this local website.
```

```text
Use $jz-deploy-cloudflare to publish this local app on Cloudflare Workers.
```

```text
Use $jz-migrate-vercel-to-cloudflare to move this Vercel project to Cloudflare.
```

```text
Use $jz-setup-site-domain to connect example.com to this deployed site.
```

```text
Use $jz-setup-site-analytics to set up analytics and search indexing for example.com.
```

```text
Use $jz-setup-indexnow to add IndexNow support to this web app.
```

```text
Use $jz-setup-conversion-tracking to add signup and checkout funnel events.
```

```text
Use $jz-get-site-metrics to check example.com metrics from GSC, Cloudflare, Umami, and Clarity.
```

```text
Use $jz-check-site-speed to check PageSpeed and Web Vitals for this URL.
```

```text
Use $jz-setup-github-agent-access to prepare fork-only GitHub access for this repo.
```

```text
Use $jz-commit-code to review and commit these changes.
```

```text
Use $jz-push-code to verify, push, and sync changed public URLs.
```

```text
Use $jz-check-vercel-cost to reconcile this Vercel receipt with usage data.
```

```text
Use $jz-check-cloudflare-cost to check running resource costs in the current Cloudflare billing cycle.
```

```text
Use $jz-check-neon-usage to find why this Neon database is still receiving requests.
```

```text
Use $jz-create-cloudflare-token to create a minimal Cloudflare token for this project.
```

```text
Use $jz-setup-mailgun-domain to initialize mg.example.com for Mailgun and write the sending configuration, including EMAIL_FROM, into this project.
```

```text
Use $jz-setup-auto-pr to connect this GitHub repo to the local Auto PR runner.
```

```text
Use $jz-setup-personal-context to interview me, create about.md, voice.md, anti-style.md in ~/Projects/aboutme, and enable all targets with -g.
```

```text
Use $jz-send-notification to add completion notifications to this scheduled task: system notification, Feishu, and Slack.
```

```text
Use $jz-manage-cron-jobs to create an hourly cron-job.org task that calls /api/health.
```

```text
Use $jz-setup-tailwind-theme to initialize Tailwind v4 theme tokens.
```

```text
Use $jz-get-revenue-sites to find high-revenue sites similar to example.com.
```

```text
Use $jz-check-market-demand to validate whether this product idea has search demand, paid competitors, and a reachable buyer path.
```

```text
Use $jz-make-viral to review this product page for positioning, pricing, copy, and shareability.
```

```text
Use $jz-manage-cloud-agent to check cloud agent status or sync skills to Hermes/OpenClaw.
```

```text
Use $jz-setup-testing to add tests for this site before shipping.
```

```text
Use $jz-create-test-plan to turn this feature idea into a QA-ready test plan.
```

```text
Use $jz-manage-ovh-servers to create an OVH VPS and get SSH access.
```

```text
Use $jz-manage-hetzner-servers to create a Hetzner Cloud server and harden SSH.
```

```text
Use $jz-get-x-posts to fetch the latest 100 X posts for @<x-username> and save them as Markdown and JSON.
```

```text
Use $jz-get-feishu-doc to download this Feishu wiki article as a local Markdown clipping and save its images under local assets.
```

```text
Use $jz-get-scys-article to fetch this scys.com article as Markdown; if it links to a Feishu full article, use the Feishu content and record the original scys.com URL.
```

```text
Use $jz-get-video-transcript to fetch this YouTube or X video transcript and create English, Chinese, and bilingual Markdown files.
```

```text
Use $jz-transcribe-media to transcribe this meeting recording.
```

```text
Use $jz-create-marketing-video to analyze this website or product promo reference video and produce a same-style marketing video (with a synthesized soundtrack) for the current project using Remotion.
```

```text
Use $jz-create-book-notes to distill this EPUB book into structured Markdown notes with counterintuitive findings and deep insights.
```

```text
Use $jz-edit-talking-head-video to package this talking-head video: transcribe and segment it, tag emotions and key phrases, plan B-roll inserts, keyword cards, masks and motion keyframes, then generate a JianyingPro draft after my confirmation.
```

```text
Use $jz-get-douyin-transcripts to transcribe this Douyin profile, channel <channel>, latest 30 videos.
```

```text
Use $jz-sync-wechat-archive to update the WeChat article archive for this account.
```

```text
Use $jz-get-readest-highlights to list Readest books, or export text and note for the third book into "<book title> 阅读笔记.md".
```

```text
Use $jz-manage-litellm to check LiteLLM model prices, key status, and recent spend logs.
```

```text
Use $jz-manage-cloudflare-ai-gateway to inspect Cloudflare AI Gateway request paths, latency, custom providers, spend limits, and facade protocol routing.
```

```text
Use $jz-manage-newapi to check NewAPI model prices, key status, and channel routing.
```

```text
Use $jz-launch-chrome to open my daily Chrome profile or the isolated Agent Chrome on port 9333.
```

```text
Use $jz-manage-launchd-tasks to create or organize this macOS launchd background task.
```

```text
Use $jz-review-bug to record this bug source in gbrain and write an HKB Wiki postmortem.
```

## Configuration

The skills use authenticated CLIs, API tokens, browser sessions, or environment variables depending on the task.

Copy `.env.example` to `.env` if your runner loads env files before invoking skills:

```bash
cp .env.example .env
```

Prepare only the credentials needed for the skills you run.

Per-skill local configuration should live under `~/.config/skills/<skill-name>/`.
Use `.env` for environment variables and `config.yml` for structured settings.

### Credentials by skill

| Skill | Required for the core path | Optional branches |
| --- | --- | --- |
| `jz-deploy-vercel` | GitHub CLI auth (`gh auth login`), Vercel CLI auth (`vercel login`), `GITHUB_OWNER`, `VERCEL_SCOPE` | Production app env vars copied to Vercel |
| `jz-launch-cloudflare-site` | Current project checkout, Cloudflare auth, and GitHub access when creating or pushing a repo | Final domain/DNS credentials, analytics credentials, conversion path details, automation support for Auto PR |
| `jz-deploy-cloudflare` | Cloudflare auth through Wrangler or `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | GitHub CLI auth when creating or connecting a repo |
| `jz-migrate-vercel-to-cloudflare` | Existing project checkout and Cloudflare auth | Vercel auth only when reading current Vercel settings |
| `jz-setup-site-domain` | Hosting provider auth, DNS provider auth when DNS must be changed, registrar auth when nameservers must be changed | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `SPACESHIP_API_KEY`, `SPACESHIP_API_SECRET`, Cloudflare Email Routing permissions if inbound forwarding is requested, authenticated browser session for providers without API coverage |
| `jz-setup-site-analytics` | Final public domain | Analytics credentials, Google OAuth/ADC for Search Console and Site Verification, Cloudflare DNS token for verification TXT records, `BING_WEBMASTER_API_KEY`, `SITE_INTEGRATIONS_CONFIG` with per-domain Clarity config, or `CLARITY_ID` and `CLARITY_TOKEN` |
| `jz-setup-indexnow` | Writable repo with a known final host | `INDEXNOW_KEY` only if overriding the generated key; otherwise the skill creates a fresh key |
| `jz-setup-conversion-tracking` | Existing analytics setup and editable app code | Stripe or auth code access only when checkout/signup events need implementation |
| `jz-get-site-metrics` | Provider credentials for selected sources | Google ADC, Cloudflare token, Umami credentials, Clarity token depending on providers |
| `jz-check-site-speed` | PageSpeed API key for higher quota | Cloudflare token for RUM data |
| `jz-setup-github-agent-access` | GitHub CLI auth for `OWNER_ACCOUNT`; agent account details from local config or user input | `~/.config/skills/jz-setup-github-agent-access/.env`, `JZ_GITHUB_AGENT_ACCESS_CONFIG`, `AGENT_GITHUB`, `AGENT_EMAIL` |
| `jz-commit-code` | Git repository with local changes | None |
| `jz-push-code` | Clean committed branch and remote push access | IndexNow/Search Console credentials only for public site URL sync |
| `jz-check-vercel-cost` | Vercel CLI auth and access to the relevant team/project usage | Receipt date, billing cycle day, platform fee override |
| `jz-check-cloudflare-cost` | Cloudflare API Token (Account: Analytics: Read), `CLOUDFLARE_ACCOUNT_ID` | Optional existing hourly cost monitor |
| `jz-check-neon-usage` | Platform request logs, cron-job.org schedules, and read-only database statistics | Vercel CLI auth, Neon/Postgres read credentials, optional `CRON_JOB_API_KEY`, project source code |
| `jz-create-cloudflare-token` | Bootstrap Cloudflare token with permission to create or edit account tokens | Project repo metadata for tighter token scoping |
| `jz-setup-mailgun-domain` | `MAILGUN_PRIMARY_API_KEY`; target-zone `CLOUDFLARE_DNS_API_TOKEN` with Zone Read and DNS Write; writable `.env` and `.dev.vars` that are untracked and ignored when the project uses Git | `$jz-create-cloudflare-token` when a project-scoped DNS token is missing |
| `jz-setup-auto-pr` | GitHub repo access, an online self-hosted runner, local repo checkout, dispatcher path, and repo mapping config; macOS notifications need no extra credential | Optional override if a repo should not auto-process every new issue; Feishu notification credentials only after the user confirms |
| `jz-setup-personal-context` | Writable profile directory | `-g` when installing the generated profile into supported tools |
| `jz-setup-tailwind-theme` | Editable frontend project using Tailwind | Existing design-system files if the project already has one |
| `jz-get-revenue-sites` | Similarweb/Semrush/TrustMRR credentials or local cached exports | Local SQLite/CSV data paths for prior research |
| `jz-check-market-demand` | Product idea, target buyer, product page, or repository context | Optional accounts for paid validation tools, SEO APIs, Exa, scraping APIs, or local cached research |
| `jz-make-viral` | Product, site, page, or positioning context | Topic-specific reference files are loaded as needed |
| `jz-manage-cloud-agent` | Local untracked deployment config and SSH access | Skill sync targets and remote browser config when needed |
| `jz-setup-testing` | Editable web project | Existing test stack, CI config, or browser dependencies depending on project |
| `jz-create-test-plan` | Feature idea, design/spec/issue, conversation, or current branch context | Optional local config to override the output path template |
| `jz-get-x-posts` | RapidAPI key for the Twittr X API | Optional local `.env` fallback inside the skill directory |
| `jz-get-feishu-doc` | `lark-cli` config and user auth with doc read/media access | Feishu document URL or token; write access to the target clipping directory |
| `jz-get-scys-article` | Logged-in Chrome for Testing session on a CDP port | `lark-cli` user auth when the article links to a Feishu full article; optional user Chrome session only when Chrome for Testing is unavailable |
| `jz-get-video-transcript` | `yt-dlp` and network access to YouTube or X video captions | `translate.googleapis.com` access for Chinese machine translation |
| `jz-transcribe-media` | `GLM_API_KEY` and `ffmpeg`/`ffprobe` | Skill-local `.env` fallback |
| `jz-create-marketing-video` | `ffmpeg`/`ffprobe`, Python 3 with numpy, Node.js with npm access for Remotion | Headless Chrome download (or Playwright CDN fallback) for rendering |
| `jz-create-book-notes` | Python 3 and EPUB file access | `~/.config/skills/jz-create-book-notes/config.yml` to set a custom output directory |
| `jz-edit-talking-head-video` | `ffmpeg`/`ffprobe` and Python 3; Shotcut for the MLT backend, or `pyJianYingDraft` plus a plaintext JianyingPro draft folder for the JianYing backend | `faster-whisper` for transcription (or an existing srt); Pexels/Pixabay API keys in `~/.config/skills/jz-edit-talking-head-video/.env` for stock footage |
| `jz-get-douyin-transcripts` | `GLM_API_KEY`, `ffmpeg`/`ffprobe`, and Douyin video/profile access | Logged-in Chrome CDP for profile collection; `--input-file` works without CDP |
| `jz-sync-wechat-archive` | API key for the archive provider | Existing state/cache files when resuming a sync |
| `jz-get-readest-highlights` | Readest base URL, anon key, owner email, and owner password in local `.env` | Export by list index or title fragment |
| `jz-send-notification` | No extra credential for local system notifications | Feishu needs `lark-cli` auth or `FEISHU_WEBHOOK_URL`; signed Feishu webhooks use `FEISHU_SIGN_KEY`; Slack prefers the Codex Slack connector, reads the target from `SLACK_CHANNEL_ID` or `SLACK_CHANNEL_NAME`, and uses `SLACK_WEBHOOK_URL` as script fallback |
| `jz-manage-cron-jobs` | cron-job.org API key as `CRON_JOB_API_KEY` in `~/.config/skills/jz-manage-cron-jobs/.env` | Account write access is needed to create, update, enable, disable, or delete jobs; create disabled jobs first when possible |
| `jz-manage-litellm` | Local untracked LiteLLM ops config and SSH/database access | Write access only when changing prices, fallback, budgets, or key state |
| `jz-manage-cloudflare-ai-gateway` | Cloudflare API token and account id with AI Gateway read access | Write access only when changing custom providers, spend limits, Worker secrets, or facade routing |
| `jz-manage-newapi` | Local untracked NewAPI ops config and database access | Write access only when changing model prices, key state, or channel routing |
| `jz-manage-ovh-servers` | OVH API credentials (application key, secret, consumer key) and SSH key | Write access for creating and terminating VPS |
| `jz-manage-hetzner-servers` | Hetzner Cloud API token | Write access for creating and deleting servers; SSH key for hardening |
| `jz-launch-chrome` | Local Chrome app | Optional `JZ_DAILY_CHROME_PROFILE`, `JZ_AGENT_CHROME_PORT`, `JZ_AGENT_CHROME_USER_DATA_DIR` overrides |
| `jz-manage-launchd-tasks` | macOS user account with permission to write user LaunchAgents | Root permission only for system LaunchDaemons |
| `jz-review-bug` | `gbrain` CLI and `~/.config/skills/jz-review-bug/config.yml` with `hkb_root` | `JZ_BUG_REVIEW_CONFIG` to use another local config file |

Common variables:

- `GITHUB_OWNER`: default GitHub owner for new repositories.
- `VERCEL_SCOPE`: default Vercel team or personal scope.
- `CLOUDFLARE_API_TOKEN`: DNS edits, verification records, optional proxy/TLS/email routing changes.
- `CLOUDFLARE_DNS_API_TOKEN`: project token limited to the target Zone with Zone Read and DNS Write.
- `CLOUDFLARE_ACCOUNT_ID`: account-scoped Cloudflare operations.
- `MAILGUN_PRIMARY_API_KEY`: Mailgun account-management key used only to create domains and Domain Sending Keys. Applications receive a domain-scoped `MAILGUN_API_KEY` instead.
- `EMAIL_FROM`: confirmed From address written with the generated Mailgun sending configuration.
- `SPACESHIP_API_KEY` and `SPACESHIP_API_SECRET`: Spaceship registrar nameserver updates.
- `UMAMI_BASE_URL`, `UMAMI_SCRIPT_URL`, `UMAMI_ADMIN_USERNAME`, `UMAMI_ADMIN_PASSWORD`: preferred self-hosted Umami setup. Log in through `$UMAMI_BASE_URL/auth/login` and use the returned Bearer token for API calls.
- `UMAMI_API_KEY`: fallback only, for Umami Cloud or compatible providers that explicitly support API-key auth.
- Google OAuth/ADC: Search Console and Site Verification access for the Google account that owns the site. Common local options are `gcloud auth application-default login`, `GOOGLE_APPLICATION_CREDENTIALS`, or another authenticated Google API session.
- `BING_WEBMASTER_API_KEY`: Bing Webmaster Tools site verification and sitemap submission.
- `SITE_INTEGRATIONS_CONFIG`: optional domain-to-repo and integration metadata map. Clarity first reads per-domain `clarity.project_id` and `clarity.token` entries from this map. If the map is missing or lacks Clarity for the target domain, `jz-setup-site-analytics` checks `CLARITY_ID` and `CLARITY_TOKEN` in the current environment. If neither source has both values, Clarity is skipped and reported.
- `CLARITY_ID` and `CLARITY_TOKEN`: optional Clarity project id and project-level Data Export API token for the current run.
- `JZ_GITHUB_AGENT_ACCESS_CONFIG`: optional local GitHub agent access config path. The old `ADD_CLOUD_AGENT_COLLABORATOR_CONFIG` remains a fallback.

Example `SITE_INTEGRATIONS_CONFIG` file:

```json
{
  "domains": {
    "example.com": {
      "repo_dir": "<repo-dir>",
      "clarity": {
        "project_id": "existing-clarity-project-id",
        "project_name": "Optional project name",
        "token": "<clarity-token>"
      }
    }
  }
}
```

Point the variable at the JSON file:

```bash
export SITE_INTEGRATIONS_CONFIG=<config-dir>/site-integrations.json
```

Keep files that contain Clarity tokens out of public commits.

Environment fallback:

```bash
export CLARITY_ID=existing-clarity-project-id
export CLARITY_TOKEN=<clarity-token>
```

Never commit `.env`, local Vercel bindings, browser state, or generated auth caches. The repository `.gitignore` excludes `.env` and `.env.*`, while allowing `.env.example`.

Missing optional credentials or config files should not stop unrelated steps. For example, missing Clarity, Umami, or `SITE_INTEGRATIONS_CONFIG` should only mark the affected integration as skipped in the final report after supported fallbacks are checked.

## Index onboarding data sources

`jz-setup-site-analytics` combines several sources because they answer different questions about the same site.

| Source | Main use | Overlap | Unique value |
| --- | --- | --- | --- |
| Umami-compatible analytics | Measures on-site visits, referrers, pages, countries, devices, and events. | Overlaps with Clarity on visits and pages. | Own first-party traffic view, simple event tracking, self-hostable option. |
| Google Search Console | Measures Google Search impressions, clicks, queries, pages, indexing, and sitemap status. | Overlaps with Bing Webmaster Tools on search indexing and sitemap submission. | Google-specific query and indexing data. |
| IndexNow | Pushes changed URLs to participating search engines. | Complements sitemap submission in Google/Bing. | Fast URL discovery signal after content changes. |
| Bing Webmaster Tools | Measures Bing search presence, verifies the site, and submits sitemaps/URLs. | Overlaps with Google Search Console on search performance and index health. | Bing-specific index state and API-based URL/feed submission. |
| Microsoft Clarity | Shows session behavior, heatmaps, recordings, rage clicks, and UX friction. | Overlaps with analytics on page visits. | Behavior-level evidence that aggregate analytics cannot show. |

Gaps worth adding later:

- Server logs or CDN logs for bot traffic, status codes, cache hits, and crawler access.
- Web analytics alternatives such as Plausible, PostHog, Fathom, or Cloudflare Web Analytics.
- Error monitoring such as Sentry for runtime failures.
- Performance data from PageSpeed Insights, CrUX, or WebPageTest.
- Ads and campaign data from Google Ads, Microsoft Ads, Meta, or UTM warehouses.
- SEO rank and keyword tools such as Ahrefs, Semrush, or DataForSEO.
- Uptime checks and synthetic monitoring.

## Design

The workflow is split into several skills instead of one large skill because each stage has different inputs, permissions, and completion criteria:

- Deployment can finish before a custom domain exists.
- DNS propagation may need waiting and rechecks.
- Search and analytics setup runs after the final domain is reachable.
- IndexNow can be added independently to an existing website.

This keeps each skill easier to audit and safer to run.

## License

MIT
