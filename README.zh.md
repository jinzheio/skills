# skills

[English](README.md) | 中文

用于发布网站、绑定自定义域名、接入搜索索引的 agent skills。

这是一个公开 skill pack。项目根目录下的每个 skill 目录都是独立 skill，包含自己的 `SKILL.md` 和可选资源文件。

## Skills

| Skill | 用途 |
| --- | --- |
| `upstart-site` | 通过 GitHub 和 Vercel 发布本地 Web 项目。NextJS 或者静态页面都可以。如果没有云端 repo，会新建 Private Repo。 |
| `new-domain-launch` | 为已部署的网站绑定自定义域名、DNS、HTTPS 和跳转。 |
| `index-onboarding` | 在正式域名可访问后，接入统计和搜索索引。 |
| `add-indexnow` | 为已有网站添加 IndexNow 验证 key、URL 收集脚本和提交脚本。 |
| `add-cloud-agent-collaborator` | 为 cloud-agent 开发账号准备 fork-only GitHub 权限。 |
| `commit-code` | Review 工作区变更，确认后按范围提交。 |
| `push-code` | 验证、推送代码，并同步变更页面的索引。 |

新网站的推荐顺序：

```text
upstart-site -> new-domain-launch -> index-onboarding
```

`add-indexnow` 单独保留，因为已有网站可能只需要补 IndexNow。

## 代码上传流程

日常开发流程：

```text
commit-code -> push-code
```

`commit-code` 会 review 工作区、报告风险、等待确认，并只提交目标文件。`push-code` 会执行验证、保持 git 工作区干净、推送分支，并调用 `add-indexnow` 确保目标仓库具备 IndexNow URL 收集和提交能力，用于同步变更过的公开页面。

`push-code` 不应该在每次页面编辑后重复向 Google Search Console 提交同一个 sitemap。只有 sitemap 路由、robots 引用、canonical host、公开路由结构或 Search Console 状态发生变化时，才检查或提交 sitemap。普通的既有页面更新，走 IndexNow URL 提交通道。

## 安装

克隆仓库：

```bash
git clone https://github.com/<owner>/<repo>.git
```

然后把需要的 skills 复制或软链接到你的 agent/runner 支持的 skills 目录。

Codex 示例：

```bash
mkdir -p ~/.codex/skills
cp -R upstart-site ~/.codex/skills/
cp -R new-domain-launch ~/.codex/skills/
cp -R index-onboarding ~/.codex/skills/
cp -R add-indexnow ~/.codex/skills/
cp -R add-cloud-agent-collaborator ~/.codex/skills/
cp -R commit-code ~/.codex/skills/
cp -R push-code ~/.codex/skills/
```

如果 runner 能直接读取这个仓库，不需要复制。

每个 skill 可以包含 `agents/openai.yaml`。这些文件提供 OpenAI/Codex 类 runner 使用的展示信息和默认 prompt。只靠 `SKILL.md` 也能运行；发布或展示 skill pack 时，保留这些元数据更方便。

## 使用

在 agent 中按名称调用 skill：

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

```text
Use $add-cloud-agent-collaborator to prepare fork-only GitHub access for this repo.
```

```text
Use $commit-code to review and commit these changes.
```

```text
Use $push-code to verify, push, and sync changed public URLs.
```

## 配置

这些 skills 会根据任务使用已登录的 CLI、API token、浏览器会话或环境变量。

如果你的运行环境会在调用 skills 前加载 env 文件，可以复制 `.env.example`：

```bash
cp .env.example .env
```

只准备要运行的流程需要的凭证。

### 各 skill 使用的凭证

| Skill | 主流程需要 | 可选分支 |
| --- | --- | --- |
| `upstart-site` | GitHub CLI 登录（`gh auth login`）、Vercel CLI 登录（`vercel login`）、`GITHUB_OWNER`、`VERCEL_SCOPE` | 同步到 Vercel 的生产环境变量 |
| `new-domain-launch` | 需要改 DNS 时要有 DNS provider 权限；需要改 nameserver 时要有 registrar 权限；需要绑定托管平台域名时要有 hosting provider 权限 | `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`、`SPACESHIP_API_KEY`、`SPACESHIP_API_SECRET`；如果要配置邮件转发，需要 Cloudflare Email Routing 权限；没有 API 时可用已登录浏览器会话 |
| `index-onboarding` | 正式可访问的域名 | 统计服务凭证、Google OAuth/ADC、Cloudflare DNS token、`BING_WEBMASTER_API_KEY`、带各域名 Clarity 配置的 `SITE_INTEGRATIONS_CONFIG`，或 `CLARITY_ID` 和 `CLARITY_TOKEN` |
| `add-indexnow` | 可写的项目仓库和已确定的正式域名 | 只有在覆盖自动生成 key 时才需要 `INDEXNOW_KEY` |
| `add-cloud-agent-collaborator` | `OWNER_ACCOUNT` 的 GitHub CLI 登录；agent 账号信息来自本机配置或用户输入 | `ADD_CLOUD_AGENT_COLLABORATOR_CONFIG`、`AGENT_GITHUB`、`AGENT_EMAIL` |

常用变量：

- `GITHUB_OWNER`：新建 GitHub 仓库时的默认 owner。
- `VERCEL_SCOPE`：Vercel team 或个人 scope。
- `CLOUDFLARE_API_TOKEN`：DNS 修改、验证 TXT 记录、代理/TLS/邮件转发等操作。
- `CLOUDFLARE_ACCOUNT_ID`：Cloudflare 账户级操作。
- `SPACESHIP_API_KEY` 和 `SPACESHIP_API_SECRET`：Spaceship 注册商 nameserver 更新。
- `UMAMI_BASE_URL`、`UMAMI_SCRIPT_URL`、`UMAMI_ADMIN_USERNAME`、`UMAMI_ADMIN_PASSWORD`：首选的 self-hosted Umami 接入。通过 `$UMAMI_BASE_URL/auth/login` 登录，使用返回的 Bearer token 调 API。
- `UMAMI_API_KEY`：仅作 fallback，用于 Umami Cloud 或明确支持 API-key auth 的兼容服务。
- Google OAuth/ADC：用于 Search Console 和 Site Verification，授权账号需要拥有站点权限。常见本地方式包括 `gcloud auth application-default login`、`GOOGLE_APPLICATION_CREDENTIALS`，或其他已认证的 Google API 会话。
- `BING_WEBMASTER_API_KEY`：Bing Webmaster Tools 站点验证和 sitemap 提交。
- `SITE_INTEGRATIONS_CONFIG`：可选的域名到仓库和集成元数据映射。Clarity 先读取这里的各域名 `clarity.project_id` 和 `clarity.token`。如果映射不存在，或目标域名没有 Clarity 配置，`index-onboarding` 会检查当前环境变量里的 `CLARITY_ID` 和 `CLARITY_TOKEN`。两个来源都缺少完整信息时，跳过 Clarity 并在汇总里说明。
- `CLARITY_ID` 和 `CLARITY_TOKEN`：可选的 Clarity project ID 和项目级 Data Export API token，用于当前运行。
- `ADD_CLOUD_AGENT_COLLABORATOR_CONFIG`：cloud-agent GitHub 权限设置使用的本机 env 文件路径。

`SITE_INTEGRATIONS_CONFIG` 文件示例：

```json
{
  "domains": {
    "example.com": {
      "repo_dir": "/absolute/path/to/repo",
      "clarity": {
        "project_id": "existing-clarity-project-id",
        "project_name": "Optional project name",
        "token": "project-level-data-export-token"
      }
    }
  }
}
```

把变量指向这个 JSON 文件：

```bash
export SITE_INTEGRATIONS_CONFIG=/absolute/path/to/config/site-integrations.json
```

包含 Clarity token 的文件不要提交到公开仓库。

环境变量 fallback：

```bash
export CLARITY_ID=existing-clarity-project-id
export CLARITY_TOKEN=project-level-data-export-token
```

不要提交 `.env`、本地 Vercel 绑定、浏览器状态或生成的认证缓存。仓库 `.gitignore` 已排除 `.env` 和 `.env.*`，同时保留 `.env.example`。

缺少可选凭证或配置文件时，不中断无关步骤。例如缺少 Clarity、Umami 或 `SITE_INTEGRATIONS_CONFIG`，在检查可用 fallback 后，只在最后把受影响的集成标记为 skipped。

## Index onboarding 数据源

`index-onboarding` 组合多个数据源，因为它们回答的是同一个网站的不同问题。

| 数据源 | 主要用途 | 重复之处 | 独特价值 |
| --- | --- | --- | --- |
| Umami 兼容统计 | 统计访问量、来源、页面、国家、设备和事件。 | 与 Clarity 在访问和页面维度有重叠。 | 自有一方流量视图，事件统计简单，可自托管。 |
| Google Search Console | 查看 Google 搜索曝光、点击、查询词、页面、索引和 sitemap 状态。 | 与 Bing Webmaster Tools 在搜索索引和 sitemap 提交上重叠。 | Google 搜索专属的查询和索引数据。 |
| IndexNow | 把变化 URL 推送给参与协议的搜索引擎。 | 与 Google/Bing 的 sitemap 提交互补。 | 内容变化后的快速发现信号。 |
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
