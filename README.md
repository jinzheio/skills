# jzskills

English | [中文](README.zh.md)

`jzskills` is a local workspace for reusable agent skills. Large product-domain skills are independent Git repositories. Small, single-purpose skills remain in this repository.

This layout keeps each published skill independent while maintaining exactly one local source copy. Codex, Claude, and Agents directories should symlink to that copy.

## Independent repositories

| Repository | Actions or scope |
| --- | --- |
| `ship/jz-build-tanstack` | Build and validate TanStack applications; production deployment is being separated. |
| `ship/jz-cloudflare` | `deploy`, `launch`, `credentials`, `cost`, `migrate-from-vercel`, `mirror-worker-to-vps` |
| `content/jz-content-ingest` | `x-posts`, `feishu-doc`, `scys-article`, `video-transcript`, `transcribe-media`, `douyin-transcripts`, `wechat-articles`, `readest-highlights` |
| `ship/jz-github` | `commit`, `push`, `auto-pr`, `agent-access` |
| `ship/jz-site-observability` | `onboard`, `conversion`, `indexnow`, `metrics`, `speed` |
| `ship/jz-vercel` | `deploy`, `cost` |
| `ship/jz-testing` | `setup`, `plan` |
| `infra/jz-llm-gateway` | `litellm`, `newapi`, `cloudflare-ai-gateway` |
| `infra/jz-cloud-servers` | `hetzner`, `ovh` |
| `local/jz-browser-automation` | `launch`, `setup` |
| `infra/jz-scheduler` | `cron`, `launchd` |
| `content/jz-video-production` | `marketing`, `talking-head` |
| `ship/jz-product-research` | `demand`, `revenue-sites` |
| `ship/jz-product-page` | `strategy`, `theme` |
| `training/jz-training` | `outline`, `profile-sync` |

[`catalog.yml`](catalog.yml) is the machine-readable workspace catalog. These are ordinary nested repositories, not vendored copies or Git submodules.

## Small skills kept in this repository

| Path | Purpose |
| --- | --- |
| `ship/jz-check-neon-usage` | Diagnose Neon activity and scale-to-zero problems. |
| `ship/jz-manage-cloud-agent` | Diagnose cloud agents and synchronize skills to supported runners. |
| `ship/jz-setup-mailgun-domain` | Configure a Mailgun sending domain and its DNS records. |
| `ship/jz-setup-site-domain` | Connect a deployed site to a custom domain. |
| `content/jz-create-book-notes` | Create structured book notes. |
| `infra/jz-send-notification` | Send task-completion notifications. |
| `local/jz-connect-mac` | Connect to another Mac. |
| `local/jz-review-bug` | Review a locally reproduced bug. |
| `local/jz-setup-personal-context` | Create and install personal context files. |

## Install one independent skill

Clone the skill repository once, then link that same directory into each runner you use:

```bash
git clone https://github.com/<github-owner>/jz-github.git <workspace>/ship/jz-github

ln -s <workspace>/ship/jz-github ~/.codex/skills/jz-github
ln -s <workspace>/ship/jz-github ~/.claude/skills/jz-github
ln -s <workspace>/ship/jz-github ~/.agents/skills/jz-github
```

Do not copy the same skill into three locations. A symlinked single source prevents runner-specific versions from drifting apart.

Small skills can still be linked directly from this repository:

```bash
ln -s <workspace>/ship/jz-setup-site-domain ~/.codex/skills/jz-setup-site-domain
```

## Local configuration

Versioned repositories contain examples only. Secrets and machine-specific paths belong under `~/.config/skills/<skill-name>/`.

| Skill | Preferred local configuration |
| --- | --- |
| `jz-cloudflare` | `~/.config/skills/jz-cloudflare/` |
| `jz-content-ingest` | `~/.config/skills/jz-content-ingest/` |
| `jz-github` | `~/.config/skills/jz-github/` |
| `jz-site-observability` | `~/.config/skills/jz-site-observability/` |
| `jz-llm-gateway` | `~/.config/skills/jz-llm-gateway/` |
| `jz-cloud-servers` | `~/.config/skills/jz-cloud-servers/` |
| `jz-scheduler` | `~/.config/skills/jz-scheduler/` |
| `jz-video-production` | `~/.config/skills/jz-video-production/` |
| `jz-product-research` | `~/.config/skills/jz-product-research/` |
| `jz-training` | `~/.config/skills/jz-training/` |

Legacy action-specific paths are migration fallbacks only. New configuration should use the consolidated skill name.

## Usage

Name the skill and, when useful, its action:

```text
Use the launch action in $jz-cloudflare to publish this site.
Use the commit action in $jz-github to review and commit these changes.
Use the indexnow action in $jz-site-observability for this existing site.
Use the revenue-sites action in $jz-product-research to find comparable sites.
Use the outline action in $jz-training to compose a four-day course.
```

The old-name mapping is documented in [`docs/skill-migration.md`](docs/skill-migration.md).

## Repository contract

Each independent skill contains:

- one router `SKILL.md`;
- one-level action references under `references/`;
- deterministic scripts and assets when needed;
- `agents/openai.yaml` metadata;
- trigger, source-coverage, or contract tests;
- its own Git history, README, and license.

Before publishing, run the repository's documented tests and scan tracked files for local paths, accounts, secrets, cookies, private keys, private hosts, and runtime databases.
