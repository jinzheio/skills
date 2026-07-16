# Skill 名称迁移表

这次重构删除了已合并的旧 skill 入口。调用时改用新的大 skill，并在需要时明确 action。旧源码没有保留兼容副本；每个大 skill 在本机只有一份源码，由不同 runner 的 skill 目录通过软链接访问。

## Builder 改名

| 旧名称 | 新调用 | 说明 |
| --- | --- | --- |
| `$jz-tanstack-ship` | `$jz-build-tanstack` | Repo 和 skill 改名；生产部署后续按 `TODOS.md` 继续拆分。 |

## Cloudflare 与内容采集

| 旧名称 | 新调用 |
| --- | --- |
| `$jz-deploy-cloudflare` | `$jz-cloudflare` 的 `deploy` action |
| `$jz-launch-cloudflare-site` | `$jz-cloudflare` 的 `launch` action |
| `$jz-create-cloudflare-token` | `$jz-cloudflare` 的 `credentials` action |
| `$jz-check-cloudflare-cost` | `$jz-cloudflare` 的 `cost` action |
| `$jz-migrate-vercel-to-cloudflare` | `$jz-cloudflare` 的 `migrate-from-vercel` action |
| `$jz-deploy-cloudflare-worker-vps` | `$jz-cloudflare` 的 `mirror-worker-to-vps` action |
| `$jz-get-x-posts` | `$jz-content-ingest` 的 `x-posts` action |
| `$jz-get-feishu-doc` | `$jz-content-ingest` 的 `feishu-doc` action |
| `$jz-get-scys-article` | `$jz-content-ingest` 的 `scys-article` action |
| `$jz-get-video-transcript` | `$jz-content-ingest` 的 `video-transcript` action |
| `$jz-transcribe-media` | `$jz-content-ingest` 的 `transcribe-media` action |
| `$jz-get-douyin-transcripts` | `$jz-content-ingest` 的 `douyin-transcripts` action |
| `$jz-get-wechat-articles` | `$jz-content-ingest` 的 `wechat-articles` action |
| `$jz-get-readest-highlights` | `$jz-content-ingest` 的 `readest-highlights` action |

## 开发与发布

| 旧名称 | 新调用 |
| --- | --- |
| `$jz-commit-code` | `$jz-github` 的 `commit` action |
| `$jz-push-code` | `$jz-github` 的 `push` action |
| `$jz-setup-auto-pr` | `$jz-github` 的 `auto-pr` action |
| `$jz-setup-github-agent-access` | `$jz-github` 的 `agent-access` action |
| `$jz-deploy-vercel` | `$jz-vercel` 的 `deploy` action |
| `$jz-check-vercel-cost` | `$jz-vercel` 的 `cost` action |
| `$jz-setup-testing` | `$jz-testing` 的 `setup` action |
| `$jz-create-test-plan` | `$jz-testing` 的 `plan` action |

## 站点观测与产品工作

| 旧名称 | 新调用 |
| --- | --- |
| `$jz-setup-site-analytics` | `$jz-site-observability` 的 `onboard` action |
| `$jz-setup-conversion-tracking` | `$jz-site-observability` 的 `conversion` action |
| `$jz-setup-indexnow` | `$jz-site-observability` 的 `indexnow` action |
| `$jz-get-site-metrics` | `$jz-site-observability` 的 `metrics` action |
| `$jz-check-site-speed` | `$jz-site-observability` 的 `speed` action |
| `$jz-check-market-demand` | `$jz-product-research` 的 `demand` action |
| `$jz-get-revenue-sites` | `$jz-product-research` 的 `revenue-sites` action |
| `$jz-make-viral` | `$jz-product-page` 的 `strategy` action |
| `$jz-setup-tailwind-theme` | `$jz-product-page` 的 `theme` action |

## 基础设施与本机自动化

| 旧名称 | 新调用 |
| --- | --- |
| `$jz-manage-litellm` | `$jz-llm-gateway` 的 `litellm` action |
| `$jz-manage-newapi` | `$jz-llm-gateway` 的 `newapi` action |
| `$jz-manage-cloudflare-ai-gateway` | `$jz-llm-gateway` 的 `cloudflare-ai-gateway` action |
| `$jz-manage-hetzner-servers` | `$jz-cloud-servers` 的 `hetzner` action |
| `$jz-manage-ovh-servers` | `$jz-cloud-servers` 的 `ovh` action |
| `$jz-launch-chrome` | `$jz-browser-automation` 的 `launch` action |
| `$jz-setup-browser-automation` | `$jz-browser-automation` 的 `setup` action |
| `$jz-manage-cron-jobs` | `$jz-scheduler` 的 `cron` action |
| `$jz-manage-launchd-tasks` | `$jz-scheduler` 的 `launchd` action |

## 内容生产与培训

| 旧名称 | 新调用 |
| --- | --- |
| `$jz-create-marketing-video` | `$jz-video-production` 的 `marketing` action |
| `$jz-edit-talking-head-video` | `$jz-video-production` 的 `talking-head` action |
| `$jz-training-outline-assembler` | `$jz-training` 的 `outline` action |
| `$jz-training-profile-sync` | `$jz-training` 的 `profile-sync` action |

## 本机配置迁移

新配置统一写入 `~/.config/skills/<skill-name>/`。部分脚本仍可读取旧 action 的配置目录，用于现有机器迁移；旧目录不是新的配置入口。

迁移后应删除三个全局 skill 目录中的旧名称软链接，并把新名称软链接到同一份源码。不要把新 Repo 再复制到 `~/.codex/skills/`、`~/.claude/skills/` 或 `~/.agents/skills/`。
