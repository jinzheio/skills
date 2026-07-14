# skills

[English](README.md) | 中文

一人公司工作流里复用的 agent skills。`ship/` 放建站、发布、增长和站点运维相关 skills；其它子目录放内容生产、基础设施运维等课题。

这是一个公开 skill pack。每个 skill 目录都是独立 skill，包含自己的 `SKILL.md` 和可选资源文件。

Skill 名称遵循 [命名规范](docs/skill-naming.md)：`jz-<method>-<resource>[-<qualifier>]`。

## Ship Skills

| Skill | 用途 |
| --- | --- |
| `jz-deploy-vercel` | 通过 GitHub 和 Vercel 发布本地 Web 项目。NextJS 或者静态页面都可以。如果没有云端 repo，会新建 Private Repo。 |
| `jz-launch-cloudflare-site` | 编排新站点从本地代码发布到 Cloudflare，并按需接域名、统计和 Auto PR。 |
| `jz-deploy-cloudflare` | 把本地 Web 项目发布到 Cloudflare Workers。 |
| `jz-migrate-vercel-to-cloudflare` | 把 Web 项目从 Vercel 迁移到 Cloudflare。 |
| `jz-setup-site-domain` | 为已部署的网站绑定自定义域名、DNS、HTTPS 和跳转。 |
| `jz-setup-site-analytics` | 在正式域名可访问后，接入统计和搜索索引。 |
| `jz-setup-indexnow` | 为已有网站添加 IndexNow 验证 key、URL 收集脚本和提交脚本。 |
| `jz-setup-conversion-tracking` | 为网站设计和实现转化漏斗事件埋点。 |
| `jz-get-site-metrics` | 查看 GSC、Cloudflare、Umami、Clarity 的站点实时数据。 |
| `jz-check-site-speed` | 查看 PageSpeed、CrUX 和 Cloudflare RUM 数据。 |
| `jz-setup-github-agent-access` | 为 cloud-agent 开发账号准备 fork-only GitHub 权限。 |
| `jz-commit-code` | Review 工作区变更，确认后按范围提交。 |
| `jz-push-code` | 验证、推送代码，并同步变更页面的索引。 |
| `jz-setup-testing` | 搭建或增强测试基础设施——vitest、覆盖率、CI、E2E。支持 Next.js、Astro、TanStack Start。 |
| `jz-create-test-plan` | 把功能想法、spec、issue、对话或当前分支 diff 转成 gstack QA 可读取的测试计划。 |
| `jz-check-vercel-cost` | 解释 Vercel usage、billed cost、Pro 固定费和信用卡扣款差异。 |
| `jz-check-cloudflare-cost` | 读取 Cloudflare 账单和 GraphQL usage，检查当前计费周期运行中资源的按量费用，识别异常计费。 |
| `jz-check-neon-usage` | 分析 Neon 请求来源和无法休眠原因。 |
| `jz-create-cloudflare-token` | 为项目创建或更新最小权限 Cloudflare token。 |
| `jz-setup-mailgun-domain` | 初始化 Mailgun 发信域名、Cloudflare DNS 和域名专用发送 key。 |
| `jz-setup-auto-pr` | 把 GitHub repo 接入支持 Codex 或 Claude Code 的本机 Auto PR self-hosted runner。 |
| `jz-setup-tailwind-theme` | 初始化或调整 Tailwind v4 主题 token。 |
| `jz-get-revenue-sites` | 按域名或产品类别查找相似的高收入网站。 |
| `jz-check-market-demand` | 验证一个产品 idea 是否有搜索需求、付费竞品和可触达买家。 |
| `jz-make-viral` | 综合 32 条 viral product 原则 + 5 条 landing page 设计规律，分话题路由：landing page 设计、文案、定价、产品定位、视觉品牌。 |
| `jz-manage-cloud-agent` | 诊断和运维云端 agent 部署，并把 skill 同步到 Hermes/OpenClaw。 |

## 其它课题

| 路径 | 课题 | Skills |
| --- | --- | --- |
| `ship/` | 建站、发布、增长和站点运维 | 见上方「Ship Skills」。 |
| `content/` | 内容生产与分发 | `jz-get-x-posts`、`jz-get-feishu-doc`、`jz-get-scys-article`、`jz-get-video-transcript`、`jz-transcribe-media`、`jz-get-douyin-transcripts`、`jz-get-wechat-articles`、`jz-get-readest-highlights`、`jz-create-marketing-video`、`jz-create-book-notes`、`jz-edit-talking-head-video` |
| `infra/` | 基础设施运维 | `jz-send-notification`、`jz-manage-cron-jobs`、`jz-manage-litellm`、`jz-manage-cloudflare-ai-gateway`、`jz-manage-newapi`、`jz-manage-ovh-servers`、`jz-manage-hetzner-servers` |
| `local/` | 本机操作 | `jz-setup-browser-automation`、`jz-launch-chrome`、`jz-manage-launchd-tasks`、`jz-connect-mac`、`jz-review-bug`、`jz-setup-personal-context` |

新网站的推荐顺序：

```text
jz-launch-cloudflare-site
```

如果要手动拆阶段走 Cloudflare，用 `jz-deploy-cloudflare -> jz-setup-site-domain -> jz-setup-site-analytics`。
`jz-setup-indexnow` 单独保留，因为已有网站可能只需要补 IndexNow。

## 代码上传流程

日常开发流程：

```text
jz-commit-code -> jz-push-code
```

`jz-commit-code` 会 review 工作区、报告风险、等待确认，并只提交目标文件。`jz-push-code` 会执行验证、保持 git 工作区干净、推送分支，并调用 `jz-setup-indexnow` 确保目标仓库具备 IndexNow URL 收集和提交能力，用于同步变更过的公开页面。

`jz-push-code` 不应该在每次页面编辑后重复向 Google Search Console 提交同一个 sitemap。只有 sitemap 路由、robots 引用、canonical host、公开路由结构或 Search Console 状态发生变化时，才检查或提交 sitemap。普通的既有页面更新，走 IndexNow URL 提交通道。

## 安装

克隆仓库：

```bash
git clone https://github.com/<owner>/<repo>.git
```

然后把需要的 skills 复制或软链接到你的 agent/runner 支持的 skills 目录。

`ship/` 是开发和建站主线：发布、域名、统计、搜索索引、代码 review、账单和产品/站点相关工作。其它子目录是一人公司的其它课题。例如 `content/` 放内容生产与分发，`infra/` 放基础设施运维。它们都遵循相同的 `SKILL.md` 规范；目录只表示主题。

Codex 示例：

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
cp -R content/jz-get-wechat-articles ~/.codex/skills/
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

如果 runner 能直接读取这个仓库，不需要复制。

每个 skill 可以包含 `agents/openai.yaml`。这些文件提供 OpenAI/Codex 类 runner 使用的展示信息和默认 prompt。只靠 `SKILL.md` 也能运行；发布或展示 skill pack 时，保留这些元数据更方便。

## 使用

在 agent 中按名称调用 skill：

```text
使用 $jz-launch-cloudflare-site 把这个新站点发布到 Cloudflare，并按需接域名、统计和 Auto PR。
```

```text
使用 $jz-deploy-vercel 发布这个本地网站。
```

```text
使用 $jz-deploy-cloudflare 把这个本地应用发布到 Cloudflare Workers。
```

```text
使用 $jz-migrate-vercel-to-cloudflare 把这个 Vercel 项目迁移到 Cloudflare。
```

```text
使用 $jz-setup-site-domain 把 example.com 绑定到这个已部署网站。
```

```text
使用 $jz-setup-site-analytics 为 example.com 接入统计和搜索索引。
```

```text
使用 $jz-setup-indexnow 为这个 Web app 添加 IndexNow 支持。
```

```text
使用 $jz-setup-conversion-tracking 添加注册和支付漏斗事件。
```

```text
使用 $jz-get-site-metrics 查看 example.com 的 GSC、Cloudflare、Umami 和 Clarity 数据。
```

```text
使用 $jz-check-site-speed 查看这个 URL 的 PageSpeed 和 Web Vitals。
```

```text
使用 $jz-setup-github-agent-access 为这个仓库准备 fork-only GitHub 权限。
```

```text
使用 $jz-commit-code review 并提交这些变更。
```

```text
使用 $jz-push-code 验证、推送，并同步变更过的公开 URL。
```

```text
使用 $jz-check-vercel-cost 用 usage 数据核对这张 Vercel receipt。
```

```text
使用 $jz-check-cloudflare-cost 查看当前计费周期 Cloudflare 运行资源的按量费用。
```

```text
使用 $jz-check-neon-usage 分析这个 Neon 数据库为什么仍然有请求。
```

```text
使用 $jz-create-cloudflare-token 为这个项目创建最小权限 Cloudflare token。
```

```text
使用 $jz-setup-mailgun-domain 初始化 mg.example.com，并把包含 EMAIL_FROM 的 Mailgun 发信配置写入当前项目。
```

```text
使用 $jz-setup-auto-pr 把这个 GitHub repo 接入本机 Auto PR runner。
```

```text
使用 $jz-setup-personal-context 通过访谈在 ~/Projects/aboutme 生成 about.md、voice.md、anti-style.md，并用 -g 接入四个入口。
```

```text
使用 $jz-send-notification 为这个定时任务接入完成通知：系统通知、飞书和 Slack。
```

```text
使用 $jz-manage-cron-jobs 在 cron-job.org 上创建一个每小时调用 /api/health 的定时任务。
```

```text
使用 $jz-setup-tailwind-theme 初始化 Tailwind v4 主题 token。
```

```text
使用 $jz-get-revenue-sites 查找和 example.com 相似的高收入网站。
```

```text
使用 $jz-check-market-demand 验证这个产品 idea 是否有搜索需求、付费竞品和可触达买家。
```

```text
使用 $jz-make-viral 检查这个产品页的定位、定价、文案和传播性。
```

```text
使用 $jz-manage-cloud-agent 检查云端 agent 状态，或把 skill 同步到 Hermes/OpenClaw。
```

```text
使用 $jz-setup-testing 在上线前为这个站点补测试。
```

```text
使用 $jz-create-test-plan 把这个功能想法整理成 QA 可执行的测试计划。
```

```text
使用 $jz-manage-ovh-servers 创建一台 OVH VPS 并获取 SSH 登录方式。
```

```text
使用 $jz-manage-hetzner-servers 创建一台 Hetzner Cloud 服务器并加固 SSH。
```

```text
使用 $jz-manage-newapi 查看 NewAPI 模型价格、key 状态和渠道路由。
```

```text
使用 $jz-get-x-posts 抓取 @<x-username> 最近 100 条 X 帖子，并保存为 Markdown 和 JSON。
```

```text
使用 $jz-get-feishu-doc 下载这个飞书 wiki 文章，保存为本地 Markdown clipping，并把图片下载到本地 assets。
```

```text
使用 $jz-get-scys-article 获取这个生财文章链接，保存为 Markdown；如果全文在飞书中，输出飞书内容并记录生财原始链接。
```

```text
使用 $jz-get-video-transcript 获取这个 YouTube 或 X 视频字幕，并生成英文、中文和双语 Markdown。
```

```text
使用 $jz-transcribe-media 转写这段会议录音。
```

```text
使用 $jz-create-marketing-video 分析这个网站或产品宣传参考视频，结合当前项目用 Remotion 制作一支画面与配乐风格类似的营销宣传视频（含合成配乐）。
```

```text
使用 $jz-create-book-notes 精读这本 EPUB 电子书，提炼反常识认知和深刻洞察，输出结构化 Markdown 笔记。
```

```text
使用 $jz-edit-talking-head-video 给这条口播视频做后期包装：转录分段、标注情绪和重点词，规划 B-roll 配图、关键词卡片、蒙版框选和动势关键帧，经我确认后生成剪映草稿。
```

```text
使用 $jz-get-douyin-transcripts 转写这个抖音作者主页，channel 为 <channel>，默认最新 30 条。
```

```text
使用 $jz-get-wechat-articles 获取这个公众号的最新文章，并保存到当前项目。
```

```text
使用 $jz-get-readest-highlights 查询 Readest 书籍列表，或按第 3 本书导出 text 和 note，生成「书名 阅读笔记.md」。
```

```text
使用 $jz-manage-litellm 查看 LiteLLM 模型价格、key 状态和最近消费记录。
```

```text
使用 $jz-manage-cloudflare-ai-gateway 查看 Cloudflare AI Gateway 请求路径、延迟、custom provider、spend limit 和 facade 协议路由。
```

```text
使用 $jz-launch-chrome 打开日常 Chrome profile，或打开 9333 端口的隔离 Agent Chrome。
```

```text
使用 $jz-manage-launchd-tasks 创建或整理这个 macOS launchd 后台任务。
```

```text
使用 $jz-review-bug 把这次 bug 来源记录到 gbrain，并写一篇 HKB Wiki 复盘文档。
```

## 配置

这些 skills 会根据任务使用已登录的 CLI、API token、浏览器会话或环境变量。

如果你的运行环境会在调用 skills 前加载 env 文件，可以复制 `.env.example`：

```bash
cp .env.example .env
```

只准备要运行的流程需要的凭证。

各 skill 的本机配置统一放在 `~/.config/skills/<skill-name>/`。
环境变量使用 `.env`，结构化配置使用 `config.yml`。

### 各 skill 使用的凭证

| Skill | 主流程需要 | 可选分支 |
| --- | --- | --- |
| `jz-deploy-vercel` | GitHub CLI 登录（`gh auth login`）、Vercel CLI 登录（`vercel login`）、`GITHUB_OWNER`、`VERCEL_SCOPE` | 同步到 Vercel 的生产环境变量 |
| `jz-launch-cloudflare-site` | 当前项目 checkout、Cloudflare 凭证；需要创建或推送 repo 时使用 GitHub 权限 | 正式域名/DNS 凭证、统计服务凭证、转化路径信息、Auto PR 所需 automation 支持 |
| `jz-deploy-cloudflare` | Wrangler 或 `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID` | 需要创建或连接 repo 时使用 GitHub CLI 登录 |
| `jz-migrate-vercel-to-cloudflare` | 当前项目 checkout 和 Cloudflare 凭证 | 读取现有 Vercel 设置时需要 Vercel 登录 |
| `jz-setup-site-domain` | 需要改 DNS 时要有 DNS provider 权限；需要改 nameserver 时要有 registrar 权限；需要绑定托管平台域名时要有 hosting provider 权限 | `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`、`SPACESHIP_API_KEY`、`SPACESHIP_API_SECRET`；如果要配置邮件转发，需要 Cloudflare Email Routing 权限；没有 API 时可用已登录浏览器会话 |
| `jz-setup-site-analytics` | 正式可访问的域名 | 统计服务凭证、Google OAuth/ADC、Cloudflare DNS token、`BING_WEBMASTER_API_KEY`、带各域名 Clarity 配置的 `SITE_INTEGRATIONS_CONFIG`，或 `CLARITY_ID` 和 `CLARITY_TOKEN` |
| `jz-setup-indexnow` | 可写的项目仓库和已确定的正式域名 | 只有在覆盖自动生成 key 时才需要 `INDEXNOW_KEY` |
| `jz-setup-conversion-tracking` | 已有统计接入和可编辑的应用代码 | 需要实现支付/注册事件时读取 Stripe 或 auth 相关代码 |
| `jz-get-site-metrics` | 所选 provider 的凭证 | 根据 provider 需要 Google ADC、Cloudflare token、Umami 凭证或 Clarity token |
| `jz-check-site-speed` | PageSpeed API key（提高额度） | Cloudflare RUM 数据需要 Cloudflare token |
| `jz-setup-github-agent-access` | `OWNER_ACCOUNT` 的 GitHub CLI 登录；agent 账号信息来自本机配置或用户输入 | `~/.config/skills/jz-setup-github-agent-access/.env`、`JZ_GITHUB_AGENT_ACCESS_CONFIG`、`AGENT_GITHUB`、`AGENT_EMAIL` |
| `jz-commit-code` | 有本地变更的 Git 仓库 | 无 |
| `jz-push-code` | 已提交的干净分支和远端 push 权限 | 只有公开站点 URL 同步需要 IndexNow/Search Console 凭证 |
| `jz-check-vercel-cost` | Vercel CLI 登录，并有目标 team/project usage 权限 | receipt 日期、billing cycle day、平台费覆盖值 |
| `jz-check-cloudflare-cost` | Cloudflare API Token（Account: Analytics: Read），`CLOUDFLARE_ACCOUNT_ID` | 可选依赖已部署的每小时成本监控 |
| `jz-check-neon-usage` | 平台请求日志、cron-job.org 定时任务和只读数据库统计 | Vercel CLI 登录、Neon/Postgres 只读凭证、可选 `CRON_JOB_API_KEY`、项目源码 |
| `jz-create-cloudflare-token` | 有创建或编辑账号 token 权限的 Cloudflare bootstrap token | 项目 repo 信息用于缩小 token 权限 |
| `jz-setup-mailgun-domain` | `MAILGUN_PRIMARY_API_KEY`；目标 Zone 的 `CLOUDFLARE_DNS_API_TOKEN`，权限为 Zone Read 和 DNS Write；`.env`、`.dev.vars` 可写，Git 项目中还须未被跟踪且已被忽略 | 项目缺少 DNS token 时调用 `$jz-create-cloudflare-token` |
| `jz-setup-auto-pr` | GitHub repo 权限、在线的 self-hosted runner、本机 repo checkout、dispatcher 路径和 repo 映射配置；macOS 系统通知不需要额外凭证 | 如果某个 repo 不应默认处理所有新 issue，再单独覆盖触发策略；飞书通知等用户确认后再配置凭证 |
| `jz-setup-personal-context` | 可写的 profile 目录 | 用 `-g` 接入支持的工具 |
| `jz-setup-tailwind-theme` | 可编辑的 Tailwind 前端项目 | 项目已有 design system 时读取现有主题文件 |
| `jz-get-revenue-sites` | Similarweb/Semrush/TrustMRR 凭证或本地缓存数据 | 复用本地 SQLite/CSV 历史数据 |
| `jz-check-market-demand` | 产品 idea、目标买家、产品页或仓库上下文 | 可选使用付费验证工具、SEO API、Exa、抓取 API 或本地缓存调研 |
| `jz-make-viral` | 产品、网站、页面或定位上下文 | 按话题读取对应 reference |
| `jz-manage-cloud-agent` | 本机未跟踪 deployment 配置和 SSH 权限 | 需要时读取 skill 同步目标和远程浏览器配置 |
| `jz-setup-testing` | 可编辑的 Web 项目 | 根据项目读取现有测试栈、CI 配置或浏览器依赖 |
| `jz-create-test-plan` | 功能想法、design/spec/issue、对话或当前分支上下文 | 可选本机配置覆盖输出路径模板 |
| `jz-launch-chrome` | 本机 Chrome app | 可选 `JZ_DAILY_CHROME_PROFILE`、`JZ_AGENT_CHROME_PORT`、`JZ_AGENT_CHROME_USER_DATA_DIR` 覆盖 |
| `jz-manage-launchd-tasks` | 有权限写入用户级 LaunchAgents 的 macOS 用户账号 | 只有系统级 LaunchDaemons 需要 root 权限 |
| `jz-get-x-posts` | Twittr X API 的 RapidAPI key | 可选的 skill 目录本地 `.env` 回退 |
| `jz-get-feishu-doc` | `lark-cli` 配置和有文档读取、素材访问权限的用户授权 | 飞书文档 URL 或 token；目标 clipping 目录可写 |
| `jz-get-scys-article` | 已登录的 Chrome for Testing CDP 会话 | 文章链接到飞书全文时需要 `lark-cli` 用户授权；Chrome for Testing 不可用时，可选使用用户 Chrome 会话 |
| `jz-get-video-transcript` | `yt-dlp` 和 YouTube 或 X 视频字幕访问 | 需要中文机器翻译时访问 `translate.googleapis.com` |
| `jz-transcribe-media` | `GLM_API_KEY` 和 `ffmpeg`/`ffprobe` | skill 目录本地 `.env` 回退 |
| `jz-create-marketing-video` | `ffmpeg`/`ffprobe`、带 numpy 的 Python 3、可安装 Remotion 的 Node.js/npm | 渲染需下载 headless Chrome（或用 Playwright CDN 兜底） |
| `jz-create-book-notes` | Python 3 和 EPUB 文件访问 | `~/.config/skills/jz-create-book-notes/config.yml` 设置自定义输出目录 |
| `jz-edit-talking-head-video` | `ffmpeg`/`ffprobe` 和 Python 3；MLT 后端需 Shotcut，剪映后端需 `pyJianYingDraft` 和明文格式草稿文件夹 | 转录需 `faster-whisper`（或已有 srt)；素材站搜索需 `~/.config/skills/jz-edit-talking-head-video/.env` 里的 Pexels/Pixabay API key |
| `jz-get-douyin-transcripts` | `GLM_API_KEY`、`ffmpeg`/`ffprobe` 和抖音视频/主页访问 | 主页采集推荐使用已登录 Chrome CDP；已有 URL 文件可直接用 `--input-file` |
| `jz-get-wechat-articles` | 文章列表服务 API key | 恢复补档时读取已有状态、列表页缓存和互动指标缓存 |
| `jz-get-readest-highlights` | 本机 `.env` 中的 Readest 地址、anon key、owner email 和 owner password | 可按列表序号或书名片段导出 |
| `jz-send-notification` | 本机系统通知不需要额外凭证 | 飞书需要 `lark-cli` 授权或 `FEISHU_WEBHOOK_URL`；飞书 webhook 签名用 `FEISHU_SIGN_KEY`；Slack 优先用 Codex Slack connector，发送频道用 `SLACK_CHANNEL_ID` 或 `SLACK_CHANNEL_NAME`，脚本兜底用 `SLACK_WEBHOOK_URL` |
| `jz-manage-cron-jobs` | cron-job.org API key，放在 `~/.config/skills/jz-manage-cron-jobs/.env` 的 `CRON_JOB_API_KEY` | 创建、更新、启停、删除 job 需要账号写权限；建议先创建 disabled job 再启用 |
| `jz-manage-litellm` | 本机未跟踪 LiteLLM 运维配置和 SSH/数据库权限 | 修改价格、fallback、预算或 key 状态时需要写权限 |
| `jz-manage-cloudflare-ai-gateway` | 有 AI Gateway 读取权限的 Cloudflare API token 和 account id | 修改 custom provider、spend limit、Worker secret 或 facade 路由时需要写权限 |
| `jz-manage-newapi` | 本机未跟踪 NewAPI 运维配置和数据库权限 | 修改模型价格、key 状态或渠道路由时需要写权限 |
| `jz-manage-ovh-servers` | OVH API 凭证（application key、secret、consumer key）和 SSH key | 创建和删除 VPS 需要写权限 |
| `jz-manage-hetzner-servers` | Hetzner Cloud API token | 创建和删除服务器需要写权限；加固 SSH 需要 SSH key |
| `jz-setup-browser-automation` | 本机 Chrome 和 Node.js | 自动使用 9333 端口或用户指定的 CDP 端口 |
| `jz-review-bug` | `gbrain` CLI，以及带 `hkb_root` 的 `~/.config/skills/jz-review-bug/config.yml` | 用 `JZ_BUG_REVIEW_CONFIG` 指向其它本机配置文件 |
| `jz-connect-mac` | 目标 Mac 已开启远程登录（SSH）且在同一局域网 | 同步文件和配置时需要读写权限 |

常用变量：

- `GITHUB_OWNER`：新建 GitHub 仓库时的默认 owner。
- `VERCEL_SCOPE`：Vercel team 或个人 scope。
- `CLOUDFLARE_API_TOKEN`：DNS 修改、验证 TXT 记录、代理/TLS/邮件转发等操作。
- `CLOUDFLARE_DNS_API_TOKEN`：仅限目标 Zone，权限为 Zone Read 和 DNS Write 的项目 token。
- `CLOUDFLARE_ACCOUNT_ID`：Cloudflare 账户级操作。
- `MAILGUN_PRIMARY_API_KEY`：只用于创建 Mailgun domain 和 Domain Sending Key。应用使用域名专用的 `MAILGUN_API_KEY`。
- `EMAIL_FROM`：和 Mailgun 发信配置一起写入的 From 地址，执行前需要用户确认。
- `SPACESHIP_API_KEY` 和 `SPACESHIP_API_SECRET`：Spaceship 注册商 nameserver 更新。
- `UMAMI_BASE_URL`、`UMAMI_SCRIPT_URL`、`UMAMI_ADMIN_USERNAME`、`UMAMI_ADMIN_PASSWORD`：首选的 self-hosted Umami 接入。通过 `$UMAMI_BASE_URL/auth/login` 登录，使用返回的 Bearer token 调 API。
- `UMAMI_API_KEY`：仅作 fallback，用于 Umami Cloud 或明确支持 API-key auth 的兼容服务。
- Google OAuth/ADC：用于 Search Console 和 Site Verification，授权账号需要拥有站点权限。常见本地方式包括 `gcloud auth application-default login`、`GOOGLE_APPLICATION_CREDENTIALS`，或其他已认证的 Google API 会话。
- `BING_WEBMASTER_API_KEY`：Bing Webmaster Tools 站点验证和 sitemap 提交。
- `SITE_INTEGRATIONS_CONFIG`：可选的域名到仓库和集成元数据映射。Clarity 先读取这里的各域名 `clarity.project_id` 和 `clarity.token`。如果映射不存在，或目标域名没有 Clarity 配置，`jz-setup-site-analytics` 会检查当前环境变量里的 `CLARITY_ID` 和 `CLARITY_TOKEN`。两个来源都缺少完整信息时，跳过 Clarity 并在汇总里说明。
- `CLARITY_ID` 和 `CLARITY_TOKEN`：可选的 Clarity project ID 和项目级 Data Export API token，用于当前运行。
- `JZ_GITHUB_AGENT_ACCESS_CONFIG`：可选的 GitHub agent 权限本机配置路径。旧变量 `ADD_CLOUD_AGENT_COLLABORATOR_CONFIG` 仅作 fallback。

`SITE_INTEGRATIONS_CONFIG` 文件示例：

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

把变量指向这个 JSON 文件：

```bash
export SITE_INTEGRATIONS_CONFIG=<config-dir>/site-integrations.json
```

包含 Clarity token 的文件不要提交到公开仓库。

环境变量 fallback：

```bash
export CLARITY_ID=existing-clarity-project-id
export CLARITY_TOKEN=<clarity-token>
```

不要提交 `.env`、本地 Vercel 绑定、浏览器状态或生成的认证缓存。仓库 `.gitignore` 已排除 `.env` 和 `.env.*`，同时保留 `.env.example`。

缺少可选凭证或配置文件时，不中断无关步骤。例如缺少 Clarity、Umami 或 `SITE_INTEGRATIONS_CONFIG`，在检查可用 fallback 后，只在最后把受影响的集成标记为 skipped。

## Index onboarding 数据源

`jz-setup-site-analytics` 组合多个数据源，因为它们回答的是同一个网站的不同问题。

| 数据源 | 主要用途 | 重复之处 | 独特价值 |
| --- | --- | --- | --- |
| Umami 兼容统计 | 统计访问量、来源、页面、国家、设备和事件。 | 与 Clarity 在访问和页面维度有重叠。 | 自有一方流量视图，事件统计简单，可自托管。 |
| Google Search Console | 查看 Google 搜索曝光、点击、查询词、页面、索引和 sitemap 状态。 | 与 Bing Webmaster Tools 在搜索索引和 sitemap 提交上重叠。 | Google 搜索专属的查询和索引数据。 |
| IndexNow | 把变化 URL 推送给参与协议的搜索引擎。 | 与 Google/Bing 的 sitemap 提交互补。 | 让搜索引擎更快发现更新后的 URL。 |
| Bing Webmaster Tools | 查看 Bing 搜索表现，验证站点，提交 sitemap/URL。 | 与 Google Search Console 在搜索表现和索引健康上重叠。 | Bing 专属索引状态和 API 提交入口。 |
| Microsoft Clarity | 查看会话行为、热图、录屏、rage click 和 UX 阻力。 | 与统计工具在页面访问上重叠。 | 聚合统计看不到的行为证据。 |

后续可补充的数据源：

- 服务器日志或 CDN 日志：bot 流量、状态码、缓存命中、爬虫访问。
- 其他 Web analytics：Plausible、PostHog、Fathom、Cloudflare Web Analytics。
- 错误监控：Sentry 等运行时错误数据。
- 性能数据：PageSpeed Insights、CrUX、WebPageTest。
- 广告和 campaign 数据：Google Ads、Microsoft Ads、Meta、UTM 数据仓库。
- SEO 排名和关键词工具：Ahrefs、Semrush、DataForSEO。
- 可用性检查和 synthetic monitoring。

## 设计

这些流程没有合并成一个大 skill，因为每个阶段的输入、权限和完成标准不同：

- 部署可以在自定义域名存在前完成。
- DNS 生效可能需要等待和复查。
- 搜索和统计接入在正式域名可访问后进行。
- IndexNow 可以单独补到已有网站。

拆开后，每个 skill 便于审查，也适合按需运行。

## 许可证

MIT
