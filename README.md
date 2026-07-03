# skills

English | [中文](README.zh.md)

Reusable agent skills for one-person company work. `ship/` contains site-building, launch, growth, and site-operations skills. Other subdirectories group topics such as content production and infrastructure operations.

This repository is a public skill pack. Each skill folder contains its own `SKILL.md` and optional bundled resources.

## Ship Skills

| Skill | Use it for |
| --- | --- |
| `jz-create-site` | Publish a local web project through GitHub and Vercel. |
| `jz-create-cf-site` | Publish a local web project to Cloudflare Workers. |
| `jz-migrate-to-cf` | Move a web project from Vercel to Cloudflare. |
| `jz-launch-domain` | Connect a deployed site to a custom domain with DNS, HTTPS, and redirects. |
| `jz-setup-analytics` | Set up analytics and search indexing after the final domain works. |
| `jz-add-search-index` | Add IndexNow key verification, URL collection, and submission scripts to an existing site. |
| `jz-track-conversion` | Design and implement conversion funnel event tracking. |
| `jz-get-analytics` | Check live site metrics across GSC, Cloudflare, Umami, and Clarity. |
| `jz-check-pagespeed` | Check PageSpeed, CrUX, and Cloudflare RUM data. |
| `jz-add-gh-collaborator` | Prepare fork-only GitHub permissions for a cloud-agent developer account. |
| `jz-commit-code` | Review workspace changes and create scoped commits after confirmation. |
| `jz-push-code` | Verify, push, and run post-push indexing sync. |
| `jz-test` | Set up or improve test infrastructure — vitest, coverage, CI, E2E. Supports Next.js, Astro, TanStack Start. |
| `jz-audit-vercel-cost` | Explain Vercel usage, billed cost, Pro fees, and receipt/card charge differences. |
| `jz-audit-cf-cost` | Read Cloudflare bills and GraphQL usage, check running resource costs in the current billing cycle, and identify billing anomalies. |
| `jz-audit-neon-usage` | Find why a Neon database is receiving requests or cannot scale to zero. |
| `jz-create-cf-token` | Create or update a minimal Cloudflare token for a project. |
| `jz-build-personal-context` | Interview the user to create persistent profile and writing-style files for Codex, ChatGPT, Claude, and Claude Code. |
| `jz-init-tailwind-theme` | Initialize or adjust Tailwind v4 theme tokens. |
| `jz-find-revenue-site` | Find high-revenue sites similar to a given domain or product category. |
| `jz-market-prospect` | Validate whether a product idea has search demand, paid competitors, and a reachable buyer path. |
| `jz-make-viral` | 32 viral product principles + 5 landing page design laws, topic-routed: landing page design, copywriting, pricing, product positioning, visual branding. |
| `jz-check-cloud-agent` | Diagnose and operate cloud agent deployments. |
| `jz-cloud-agent` | Diagnose cloud agent deployments and sync skills to Hermes/OpenClaw. |

## Other Topics

| Path | Topic | Skills |
| --- | --- | --- |
| `ship/` | Site-building, launch, growth, and site operations | See "Ship Skills" above. |
| `content/` | Content production and distribution | `jz-fetch-x`, `jz-feishu-doc-download`, `jz-scys-article`, `jz-video-transcript`, `jz-transcribe-audio`, `jz-douyin-transcript`, `jz-wechat-archive-sync`, `jz-readest-review`, `jz-video-style-clone`, `jz-book-distill`, `jz-video-package` |
| `infra/` | Infrastructure operations | `jz-litellm-ops`, `jz-cf-ai-gateway-ops`, `jz-newapi-ops`, `jz-ovh-server`, `jz-hetzner-server` |
| `local/` | Local machine operations | `jz-browser-automation`, `jz-chrome-launcher`, `jz-launchd-task`, `jz-mac-remote` |

Recommended sequence for a new site:

```text
jz-create-site -> jz-launch-domain -> jz-setup-analytics
```

`jz-add-search-index` is separate because it is also useful for existing sites that only need IndexNow support.

## Code Upload Workflow

For normal development work, use:

```text
jz-commit-code -> jz-push-code
```

`jz-commit-code` reviews the working tree, reports risks, waits for confirmation, and commits only the intended files. `jz-push-code` runs verification, keeps the git tree clean, pushes the branch, and then uses `jz-add-search-index` to ensure IndexNow URL collection and submission are available for changed public pages.

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
cp -R ship/jz-create-site ~/.codex/skills/
cp -R ship/jz-create-cf-site ~/.codex/skills/
cp -R ship/jz-migrate-to-cf ~/.codex/skills/
cp -R ship/jz-launch-domain ~/.codex/skills/
cp -R ship/jz-setup-analytics ~/.codex/skills/
cp -R ship/jz-add-search-index ~/.codex/skills/
cp -R ship/jz-track-conversion ~/.codex/skills/
cp -R ship/jz-get-analytics ~/.codex/skills/
cp -R ship/jz-check-pagespeed ~/.codex/skills/
cp -R ship/jz-add-gh-collaborator ~/.codex/skills/
cp -R ship/jz-commit-code ~/.codex/skills/
cp -R ship/jz-push-code ~/.codex/skills/
cp -R ship/jz-audit-vercel-cost ~/.codex/skills/
cp -R ship/jz-audit-cf-cost ~/.codex/skills/
cp -R ship/jz-audit-neon-usage ~/.codex/skills/
cp -R ship/jz-create-cf-token ~/.codex/skills/
cp -R ship/jz-build-personal-context ~/.codex/skills/
cp -R ship/jz-init-tailwind-theme ~/.codex/skills/
cp -R ship/jz-find-revenue-site ~/.codex/skills/
cp -R ship/jz-market-prospect ~/.codex/skills/
cp -R ship/jz-make-viral ~/.codex/skills/
cp -R ship/jz-check-cloud-agent ~/.codex/skills/
cp -R ship/jz-cloud-agent ~/.codex/skills/
cp -R ship/jz-test ~/.codex/skills/
cp -R content/jz-fetch-x ~/.codex/skills/
cp -R content/jz-feishu-doc-download ~/.codex/skills/
cp -R content/jz-scys-article ~/.codex/skills/
cp -R content/jz-video-transcript ~/.codex/skills/
cp -R content/jz-transcribe-audio ~/.codex/skills/
cp -R content/jz-douyin-transcript ~/.codex/skills/
cp -R content/jz-wechat-archive-sync ~/.codex/skills/
cp -R content/jz-readest-review ~/.codex/skills/
cp -R content/jz-video-style-clone ~/.codex/skills/
cp -R content/jz-book-distill ~/.codex/skills/
cp -R content/jz-video-package ~/.codex/skills/
cp -R infra/jz-litellm-ops ~/.codex/skills/
cp -R infra/jz-cf-ai-gateway-ops ~/.codex/skills/
cp -R infra/jz-newapi-ops ~/.codex/skills/
cp -R infra/jz-ovh-server ~/.codex/skills/
cp -R infra/jz-hetzner-server ~/.codex/skills/
cp -R local/jz-browser-automation ~/.codex/skills/
cp -R local/jz-chrome-launcher ~/.codex/skills/
cp -R local/jz-launchd-task ~/.codex/skills/
cp -R local/jz-mac-remote ~/.codex/skills/
```

If your runner can read this repository directly, no copy step is needed.

Each skill may include an `agents/openai.yaml` file. These files provide display metadata and default prompts for OpenAI/Codex-style runners. The skills still work from `SKILL.md` without that metadata, but the metadata is useful when publishing or listing the pack.

## Usage

Invoke a skill by name in your agent:

```text
Use $jz-create-site to publish this local website.
```

```text
Use $jz-create-cf-site to publish this local app on Cloudflare Workers.
```

```text
Use $jz-migrate-to-cf to move this Vercel project to Cloudflare.
```

```text
Use $jz-launch-domain to connect example.com to this deployed site.
```

```text
Use $jz-setup-analytics to set up analytics and search indexing for example.com.
```

```text
Use $jz-add-search-index to add IndexNow support to this web app.
```

```text
Use $jz-track-conversion to add signup and checkout funnel events.
```

```text
Use $jz-get-analytics to check example.com metrics from GSC, Cloudflare, Umami, and Clarity.
```

```text
Use $jz-check-pagespeed to check PageSpeed and Web Vitals for this URL.
```

```text
Use $jz-add-gh-collaborator to prepare fork-only GitHub access for this repo.
```

```text
Use $jz-commit-code to review and commit these changes.
```

```text
Use $jz-push-code to verify, push, and sync changed public URLs.
```

```text
Use $jz-audit-vercel-cost to reconcile this Vercel receipt with usage data.
```

```text
Use $jz-audit-cf-cost to check running resource costs in the current Cloudflare billing cycle.
```

```text
Use $jz-audit-neon-usage to find why this Neon database is still receiving requests.
```

```text
Use $jz-create-cf-token to create a minimal Cloudflare token for this project.
```

```text
Use $jz-build-personal-context to interview me, create about.md, voice.md, anti-style.md in ~/Projects/aboutme, and enable all targets with -g.
```

```text
Use $jz-init-tailwind-theme to initialize Tailwind v4 theme tokens.
```

```text
Use $jz-find-revenue-site to find high-revenue sites similar to example.com.
```

```text
Use $jz-market-prospect to validate whether this product idea has search demand, paid competitors, and a reachable buyer path.
```

```text
Use $jz-make-viral to review this product page for positioning, pricing, copy, and shareability.
```

```text
Use $jz-check-cloud-agent to diagnose the Hermes agent deployment.
```

```text
Use $jz-cloud-agent to check cloud agent status or sync skills to Hermes/OpenClaw.
```

```text
Use $jz-test to add tests for this site before shipping.
```

```text
Use $jz-ovh-server to create an OVH VPS and get SSH access.
```

```text
Use $jz-hetzner-server to create a Hetzner Cloud server and harden SSH.
```

```text
Use $jz-fetch-x to fetch the latest 100 X posts for @mercor_ai and save them as Markdown and JSON.
```

```text
Use $jz-feishu-doc-download to download this Feishu wiki article as a local Markdown clipping and save its images under local assets.
```

```text
Use $jz-scys-article to fetch this scys.com article as Markdown; if it links to a Feishu full article, use the Feishu content and record the original scys.com URL.
```

```text
Use $jz-video-transcript to fetch this YouTube or X video transcript and create English, Chinese, and bilingual Markdown files.
```

```text
Use $jz-transcribe-audio to transcribe this meeting recording.
```

```text
Use $jz-video-style-clone to analyze this reference video and produce a same-style promo video (with a synthesized soundtrack) for the current project using Remotion.
```

```text
Use $jz-book-distill to distill this EPUB book into structured Markdown notes with counterintuitive findings and deep insights.
```

```text
Use $jz-video-package to package this talking-head video: transcribe and segment it, tag emotions and key phrases, plan B-roll inserts, keyword cards, masks and motion keyframes, then generate a JianyingPro draft after my confirmation.
```

```text
Use $jz-douyin-transcript to transcribe this Douyin profile, channel jinqiangdashu, latest 30 videos.
```

```text
Use $jz-wechat-archive-sync to update the WeChat article archive for this account.
```

```text
Use $jz-readest-review to list Readest books, or export text and note for the third book into "<book title> 阅读笔记.md".
```

```text
Use $jz-litellm-ops to check LiteLLM model prices, key status, and recent spend logs.
```

```text
Use $jz-cf-ai-gateway-ops to inspect Cloudflare AI Gateway request paths, latency, custom providers, spend limits, and facade protocol routing.
```

```text
Use $jz-newapi-ops to check NewAPI model prices, key status, and channel routing.
```

```text
Use $jz-chrome-launcher to open my daily Chrome profile or the isolated Agent Chrome on port 9333.
```

```text
Use $jz-launchd-task to create or organize this macOS launchd background task.
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
| `jz-create-site` | GitHub CLI auth (`gh auth login`), Vercel CLI auth (`vercel login`), `GITHUB_OWNER`, `VERCEL_SCOPE` | Production app env vars copied to Vercel |
| `jz-create-cf-site` | Cloudflare auth through Wrangler or `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | GitHub CLI auth when creating or connecting a repo |
| `jz-migrate-to-cf` | Existing project checkout and Cloudflare auth | Vercel auth only when reading current Vercel settings |
| `jz-launch-domain` | Hosting provider auth, DNS provider auth when DNS must be changed, registrar auth when nameservers must be changed | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `SPACESHIP_API_KEY`, `SPACESHIP_API_SECRET`, Cloudflare Email Routing permissions if inbound forwarding is requested, authenticated browser session for providers without API coverage |
| `jz-setup-analytics` | Final public domain | Analytics credentials, Google OAuth/ADC for Search Console and Site Verification, Cloudflare DNS token for verification TXT records, `BING_WEBMASTER_API_KEY`, `SITE_INTEGRATIONS_CONFIG` with per-domain Clarity config, or `CLARITY_ID` and `CLARITY_TOKEN` |
| `jz-add-search-index` | Writable repo with a known final host | `INDEXNOW_KEY` only if overriding the generated key; otherwise the skill creates a fresh key |
| `jz-track-conversion` | Existing analytics setup and editable app code | Stripe or auth code access only when checkout/signup events need implementation |
| `jz-get-analytics` | Provider credentials for selected sources | Google ADC, Cloudflare token, Umami credentials, Clarity token depending on providers |
| `jz-check-pagespeed` | PageSpeed API key for higher quota | Cloudflare token for RUM data |
| `jz-add-gh-collaborator` | GitHub CLI auth for `OWNER_ACCOUNT`; agent account details from local config or user input | `ADD_CLOUD_AGENT_COLLABORATOR_CONFIG`, `AGENT_GITHUB`, `AGENT_EMAIL` |
| `jz-commit-code` | Git repository with local changes | None |
| `jz-push-code` | Clean committed branch and remote push access | IndexNow/Search Console credentials only for public site URL sync |
| `jz-audit-vercel-cost` | Vercel CLI auth and access to the relevant team/project usage | Receipt date, billing cycle day, platform fee override |
| `jz-audit-cf-cost` | Cloudflare API Token (Account: Analytics: Read), `CLOUDFLARE_ACCOUNT_ID` | Optional existing hourly cost monitor |
| `jz-audit-neon-usage` | Platform request logs, cron-job.org schedules, and read-only database statistics | Vercel CLI auth, Neon/Postgres read credentials, optional `CRON_JOB_API_KEY`, project source code |
| `jz-create-cf-token` | Bootstrap Cloudflare token with permission to create or edit account tokens | Project repo metadata for tighter token scoping |
| `jz-build-personal-context` | Writable profile directory | `-g` when installing the generated profile into supported tools |
| `jz-init-tailwind-theme` | Editable frontend project using Tailwind | Existing design-system files if the project already has one |
| `jz-find-revenue-site` | Similarweb/Semrush/TrustMRR credentials or local cached exports | Local SQLite/CSV data paths for prior research |
| `jz-market-prospect` | Product idea, target buyer, product page, or repository context | Optional accounts for paid validation tools, SEO APIs, Exa, scraping APIs, or local cached research |
| `jz-make-viral` | Product, site, page, or positioning context | Topic-specific reference files are loaded as needed |
| `jz-check-cloud-agent` | Local untracked deployment config and SSH access | Remote desktop/noVNC config only when opening a browser session |
| `jz-cloud-agent` | Local untracked deployment config and SSH access | Skill sync targets and remote browser config when needed |
| `jz-test` | Editable web project | Existing test stack, CI config, or browser dependencies depending on project |
| `jz-fetch-x` | RapidAPI key for the Twittr X API | Optional local `.env` fallback inside the skill directory |
| `jz-feishu-doc-download` | `lark-cli` config and user auth with doc read/media access | Feishu document URL or token; write access to the target clipping directory |
| `jz-scys-article` | Logged-in Chrome for Testing session on a CDP port | `lark-cli` user auth when the article links to a Feishu full article; optional user Chrome session only when Chrome for Testing is unavailable |
| `jz-video-transcript` | `yt-dlp` and network access to YouTube or X video captions | `translate.googleapis.com` access for Chinese machine translation |
| `jz-transcribe-audio` | `GLM_API_KEY` and `ffmpeg`/`ffprobe` | Skill-local `.env` fallback |
| `jz-video-style-clone` | `ffmpeg`/`ffprobe`, Python 3 with numpy, Node.js with npm access for Remotion | Headless Chrome download (or Playwright CDN fallback) for rendering |
| `jz-book-distill` | Python 3 and EPUB file access | `~/.config/skills/jz-book-distill/config.yml` to set a custom output directory |
| `jz-video-package` | `ffmpeg`/`ffprobe`, Python 3 with `pyJianYingDraft`, JianyingPro draft folder | `faster-whisper` for transcription (or an existing srt); Pexels/Pixabay API keys in `~/.config/skills/jz-video-package/.env` for stock footage |
| `jz-douyin-transcript` | `GLM_API_KEY`, `ffmpeg`/`ffprobe`, and Douyin video/profile access | Logged-in Chrome CDP for profile collection; `--input-file` works without CDP |
| `jz-wechat-archive-sync` | API key for the archive provider | Existing state/cache files when resuming a sync |
| `jz-readest-review` | Readest base URL, anon key, owner email, and owner password in local `.env` | Export by list index or title fragment |
| `jz-litellm-ops` | Local untracked LiteLLM ops config and SSH/database access | Write access only when changing prices, fallback, budgets, or key state |
| `jz-cf-ai-gateway-ops` | Cloudflare API token and account id with AI Gateway read access | Write access only when changing custom providers, spend limits, Worker secrets, or facade routing |
| `jz-newapi-ops` | Local untracked NewAPI ops config and database access | Write access only when changing model prices, key state, or channel routing |
| `jz-ovh-server` | OVH API credentials (application key, secret, consumer key) and SSH key | Write access for creating and terminating VPS |
| `jz-hetzner-server` | Hetzner Cloud API token | Write access for creating and deleting servers; SSH key for hardening |
| `jz-chrome-launcher` | Local Chrome app | Optional `JZ_DAILY_CHROME_PROFILE`, `JZ_AGENT_CHROME_PORT`, `JZ_AGENT_CHROME_USER_DATA_DIR` overrides |
| `jz-launchd-task` | macOS user account with permission to write user LaunchAgents | Root permission only for system LaunchDaemons |

Common variables:

- `GITHUB_OWNER`: default GitHub owner for new repositories.
- `VERCEL_SCOPE`: default Vercel team or personal scope.
- `CLOUDFLARE_API_TOKEN`: DNS edits, verification records, optional proxy/TLS/email routing changes.
- `CLOUDFLARE_ACCOUNT_ID`: account-scoped Cloudflare operations.
- `SPACESHIP_API_KEY` and `SPACESHIP_API_SECRET`: Spaceship registrar nameserver updates.
- `UMAMI_BASE_URL`, `UMAMI_SCRIPT_URL`, `UMAMI_ADMIN_USERNAME`, `UMAMI_ADMIN_PASSWORD`: preferred self-hosted Umami setup. Log in through `$UMAMI_BASE_URL/auth/login` and use the returned Bearer token for API calls.
- `UMAMI_API_KEY`: fallback only, for Umami Cloud or compatible providers that explicitly support API-key auth.
- Google OAuth/ADC: Search Console and Site Verification access for the Google account that owns the site. Common local options are `gcloud auth application-default login`, `GOOGLE_APPLICATION_CREDENTIALS`, or another authenticated Google API session.
- `BING_WEBMASTER_API_KEY`: Bing Webmaster Tools site verification and sitemap submission.
- `SITE_INTEGRATIONS_CONFIG`: optional domain-to-repo and integration metadata map. Clarity first reads per-domain `clarity.project_id` and `clarity.token` entries from this map. If the map is missing or lacks Clarity for the target domain, `jz-setup-analytics` checks `CLARITY_ID` and `CLARITY_TOKEN` in the current environment. If neither source has both values, Clarity is skipped and reported.
- `CLARITY_ID` and `CLARITY_TOKEN`: optional Clarity project id and project-level Data Export API token for the current run.
- `ADD_CLOUD_AGENT_COLLABORATOR_CONFIG`: optional local env file for cloud-agent GitHub permission setup.

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

`jz-setup-analytics` combines several sources because they answer different questions about the same site.

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
