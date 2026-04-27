# skills

English | [中文](README.zh.md)

Reusable agent skills for publishing a website, connecting a custom domain, and setting up search indexing.

This repository is a public skill pack. Each folder under `skills/` is a standalone skill with its own `SKILL.md` and optional bundled resources.

## Skills

| Skill | Use it for |
| --- | --- |
| `upstart-site` | Publish a local web project through GitHub and Vercel. |
| `new-domain-launch` | Connect a deployed site to a custom domain with DNS, HTTPS, and redirects. |
| `index-onboarding` | Set up analytics and search indexing after the final domain works. |
| `add-indexnow` | Add IndexNow key verification, URL collection, and submission scripts to an existing site. |

Recommended sequence for a new site:

```text
upstart-site -> new-domain-launch -> index-onboarding
```

`add-indexnow` is separate because it is also useful for existing sites that only need IndexNow support.

## Install

Clone the repository:

```bash
git clone https://github.com/jinzheio/skills.git
```

Then copy or symlink the skills you want into the skills directory supported by your agent or runner.

Codex example:

```bash
mkdir -p ~/.codex/skills
cp -R skills/skills/upstart-site ~/.codex/skills/
cp -R skills/skills/new-domain-launch ~/.codex/skills/
cp -R skills/skills/index-onboarding ~/.codex/skills/
cp -R skills/skills/add-indexnow ~/.codex/skills/
```

Project-local example for runners that read skills from the repository:

```bash
mkdir -p .claude/skills
cp -R skills/skills/upstart-site .claude/skills/
cp -R skills/skills/new-domain-launch .claude/skills/
cp -R skills/skills/index-onboarding .claude/skills/
cp -R skills/skills/add-indexnow .claude/skills/
```

If your runner can read `skills/` directly, no copy step is needed.

## Usage

Invoke a skill by name in your agent:

```text
Use $upstart-site to publish this local website.
```

```text
Use $new-domain-launch to connect example.com to this deployed site.
```

```text
Use $index-onboarding to set up analytics and search indexing for example.com.
```

```text
Use $add-indexnow to add IndexNow support to this web app.
```

## Configuration

The skills use authenticated CLIs, API tokens, browser sessions, or environment variables depending on the task.

Copy `.env.example` to `.env` if your runner loads env files before invoking skills:

```bash
cp .env.example .env
```

Prepare only the credentials needed for the skills you run.

### Credentials by skill

| Skill | Required for the core path | Optional branches |
| --- | --- | --- |
| `upstart-site` | GitHub CLI auth (`gh auth login`), Vercel CLI auth (`vercel login`), `GITHUB_OWNER`, `VERCEL_SCOPE` | Production app env vars copied to Vercel, Cloudflare Email Routing credentials if email forwarding is requested |
| `new-domain-launch` | Hosting provider auth, DNS provider auth when DNS must be changed, registrar auth when nameservers must be changed | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `SPACESHIP_API_KEY`, `SPACESHIP_API_SECRET`, authenticated browser session for providers without API coverage |
| `index-onboarding` | Final public domain | Analytics credentials, Google OAuth/ADC for Search Console and Site Verification, Cloudflare DNS token for verification TXT records, `BING_WEBMASTER_API_KEY`, Clarity project token or MCP config, `SITE_INTEGRATIONS_CONFIG` |
| `add-indexnow` | Writable repo with a known final host | `INDEXNOW_KEY` only if overriding the generated key; otherwise the skill creates a fresh key |

Common variables:

- `GITHUB_OWNER`: default GitHub owner for new repositories.
- `VERCEL_SCOPE`: default Vercel team or personal scope.
- `CLOUDFLARE_API_TOKEN`: DNS edits, verification records, optional proxy/TLS/email routing changes.
- `CLOUDFLARE_ACCOUNT_ID`: account-scoped Cloudflare operations.
- `SPACESHIP_API_KEY` and `SPACESHIP_API_SECRET`: Spaceship registrar nameserver updates.
- `UMAMI_BASE_URL`, `UMAMI_API_KEY`, `UMAMI_SCRIPT_URL`: Umami-compatible analytics setup.
- Google OAuth/ADC: Search Console and Site Verification access for the Google account that owns the site. Common local options are `gcloud auth application-default login`, `GOOGLE_APPLICATION_CREDENTIALS`, or another authenticated Google API session.
- `BING_WEBMASTER_API_KEY`: Bing Webmaster Tools site verification and sitemap submission.
- `CLARITY_PROJECT_ID`, `CLARITY_API_TOKEN`: existing Clarity project metadata and project-level Data Export API token. The public Clarity MCP server also uses an existing project token.
- `SITE_INTEGRATIONS_CONFIG`: optional domain-to-repo and integration metadata map.

Never commit `.env`, local Vercel bindings, browser state, or generated auth caches.

Missing optional credentials should not stop unrelated steps. For example, missing Clarity or Umami credentials should only mark those integrations as skipped or manual in the final report.

## Index onboarding data sources

`index-onboarding` combines several sources because they answer different questions about the same site.

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
