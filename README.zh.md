# jzskills

[English](README.md) | 中文

`jzskills` 是本机管理 agent skills 的工作区。按产品域合并的大 skill 各自是独立 Git Repo；职责单一的小 skill 继续留在本仓库。

这种结构同时满足两个要求：每个大 skill 可以单独发布，本机又始终只维护一份源码。Codex、Claude 和 Agents 的 skill 目录都应软链接到这份源码。

## 独立 Repo

| Repo | Actions 或职责 |
| --- | --- |
| `ship/jz-build-tanstack` | 构建和验证 TanStack 应用；生产部署正在按 TODO 拆分。 |
| `ship/jz-cloudflare` | `deploy`、`launch`、`credentials`、`cost`、`migrate-from-vercel`、`mirror-worker-to-vps` |
| `content/jz-content-ingest` | `x-posts`、`feishu-doc`、`scys-article`、`video-transcript`、`transcribe-media`、`douyin-transcripts`、`wechat-articles`、`readest-highlights` |
| `ship/jz-github` | `commit`、`push`、`auto-pr`、`agent-access` |
| `ship/jz-site-observability` | `onboard`、`conversion`、`indexnow`、`metrics`、`speed` |
| `ship/jz-vercel` | `deploy`、`cost` |
| `ship/jz-testing` | `setup`、`plan` |
| `infra/jz-llm-gateway` | `litellm`、`newapi`、`cloudflare-ai-gateway` |
| `infra/jz-cloud-servers` | `hetzner`、`ovh` |
| `local/jz-browser-automation` | `launch`、`setup` |
| `infra/jz-scheduler` | `cron`、`launchd` |
| `content/jz-video-production` | `marketing`、`talking-head` |
| `ship/jz-product-research` | `demand`、`revenue-sites` |
| `ship/jz-product-page` | `strategy`、`theme` |
| `training/jz-training` | `outline`、`profile-sync` |

[`catalog.yml`](catalog.yml) 是机器可读的工作区清单。这些目录是普通嵌套 Repo，不是复制进根仓库的代码，也不是 Git submodule。

## 保留在根仓库的小 skill

| 路径 | 用途 |
| --- | --- |
| `ship/jz-check-neon-usage` | 分析 Neon 请求和无法休眠的问题。 |
| `ship/jz-manage-cloud-agent` | 诊断 cloud agent，并向支持的 runner 同步 skill。 |
| `ship/jz-setup-mailgun-domain` | 配置 Mailgun 发信域名及 DNS。 |
| `ship/jz-setup-site-domain` | 为已部署站点绑定自定义域名。 |
| `content/jz-create-book-notes` | 生成结构化读书笔记。 |
| `infra/jz-send-notification` | 发送任务完成通知。 |
| `local/jz-connect-mac` | 连接另一台 Mac。 |
| `local/jz-review-bug` | 复查本机已复现的 bug。 |
| `local/jz-setup-personal-context` | 创建并安装个人上下文文件。 |

## 安装一个独立 skill

只 clone 一份源码，再把不同 runner 的入口链接到同一个目录：

```bash
git clone https://github.com/<github-owner>/jz-github.git <workspace>/ship/jz-github

ln -s <workspace>/ship/jz-github ~/.codex/skills/jz-github
ln -s <workspace>/ship/jz-github ~/.claude/skills/jz-github
ln -s <workspace>/ship/jz-github ~/.agents/skills/jz-github
```

不要向三个入口各复制一份。软链接能避免 Codex、Claude 和其它 runner 各自演化出不同版本。

根仓库里的小 skill 仍可直接链接：

```bash
ln -s <workspace>/ship/jz-setup-site-domain ~/.codex/skills/jz-setup-site-domain
```

## 本机配置

Repo 只保存示例。密钥和机器相关路径统一放在 `~/.config/skills/<skill-name>/`。

| Skill | 首选本机配置目录 |
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

旧 action 的配置目录只作为迁移 fallback。新增配置应使用合并后的 skill 名。

## 调用示例

写明 skill；有必要时再指定 action：

```text
使用 $jz-cloudflare 的 launch action 发布这个站点。
使用 $jz-github 的 commit action review 并提交这些改动。
使用 $jz-site-observability 的 indexnow action 为现有站点补 IndexNow。
使用 $jz-product-research 的 revenue-sites action 查找同类网站。
使用 $jz-training 的 outline action 组合四天课程大纲。
```

旧名称到新 action 的对应关系见 [`docs/skill-migration.md`](docs/skill-migration.md)。

## 独立 Repo 约定

每个大 skill 都包含：

- 一个负责触发和路由的 `SKILL.md`；
- 一层 `references/` action 文档；
- 必要的确定性 scripts 和 assets；
- `agents/openai.yaml`；
- trigger、来源覆盖或契约测试；
- 独立 Git 历史、README 和 LICENSE。

发布前必须运行 Repo 自己的测试，并扫描 tracked files：本机路径、真实账号、secret、cookie、private key、私有域名和运行时数据库都不能进入发布内容。
