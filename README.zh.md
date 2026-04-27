# skills

[English](README.md) | 中文

用于发布网站、绑定自定义域名、接入搜索索引的 agent skills。

这是一个公开 skill pack。`skills/` 下的每个目录都是一个独立 skill，包含自己的 `SKILL.md` 和可选资源文件。

## Skills

| Skill | 用途 |
| --- | --- |
| `upstart-site` | 通过 GitHub 和 Vercel 发布本地 Web 项目。 |
| `new-domain-launch` | 为已部署的网站绑定自定义域名、DNS、HTTPS 和跳转。 |
| `index-onboarding` | 在正式域名可访问后，接入统计和搜索索引。 |
| `add-indexnow` | 为已有网站添加 IndexNow 验证 key、URL 收集脚本和提交脚本。 |

新网站的推荐顺序：

```text
upstart-site -> new-domain-launch -> index-onboarding
```

`add-indexnow` 单独保留，因为已有网站可能只需要补 IndexNow。

## 安装

克隆仓库：

```bash
git clone https://github.com/jinzheio/skills.git
```

然后把需要的 skills 复制或软链接到你的 agent/runner 支持的 skills 目录。

Codex 示例：

```bash
mkdir -p ~/.codex/skills
cp -R skills/skills/upstart-site ~/.codex/skills/
cp -R skills/skills/new-domain-launch ~/.codex/skills/
cp -R skills/skills/index-onboarding ~/.codex/skills/
cp -R skills/skills/add-indexnow ~/.codex/skills/
```

如果 runner 从项目目录读取 skills，可以使用项目内目录：

```bash
mkdir -p .claude/skills
cp -R skills/skills/upstart-site .claude/skills/
cp -R skills/skills/new-domain-launch .claude/skills/
cp -R skills/skills/index-onboarding .claude/skills/
cp -R skills/skills/add-indexnow .claude/skills/
```

如果你的 runner 能直接读取 `skills/`，不需要复制。

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
| `upstart-site` | GitHub CLI 登录（`gh auth login`）、Vercel CLI 登录（`vercel login`）、`GITHUB_OWNER`、`VERCEL_SCOPE` | 同步到 Vercel 的生产环境变量；如果要配置邮件转发，需要 Cloudflare Email Routing 权限 |
| `new-domain-launch` | 需要改 DNS 时要有 DNS provider 权限；需要改 nameserver 时要有 registrar 权限；需要绑定托管平台域名时要有 hosting provider 权限 | `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`、`SPACESHIP_API_KEY`、`SPACESHIP_API_SECRET`；没有 API 时可用已登录浏览器会话 |
| `index-onboarding` | 正式可访问的域名 | 统计服务凭证、Google OAuth/ADC、Cloudflare DNS token、`BING_WEBMASTER_API_KEY`、Clarity project token 或 MCP 配置、`SITE_INTEGRATIONS_CONFIG` |
| `add-indexnow` | 可写的项目仓库和已确定的正式域名 | 只有在覆盖自动生成 key 时才需要 `INDEXNOW_KEY` |

常用变量：

- `GITHUB_OWNER`：新建 GitHub 仓库时的默认 owner。
- `VERCEL_SCOPE`：Vercel team 或个人 scope。
- `CLOUDFLARE_API_TOKEN`：DNS 修改、验证 TXT 记录、代理/TLS/邮件转发等操作。
- `CLOUDFLARE_ACCOUNT_ID`：Cloudflare 账户级操作。
- `SPACESHIP_API_KEY` 和 `SPACESHIP_API_SECRET`：Spaceship 注册商 nameserver 更新。
- `UMAMI_BASE_URL`、`UMAMI_API_KEY`、`UMAMI_SCRIPT_URL`：Umami 兼容统计接入。
- Google OAuth/ADC：用于 Search Console 和 Site Verification，授权账号需要拥有站点权限。常见本地方式包括 `gcloud auth application-default login`、`GOOGLE_APPLICATION_CREDENTIALS`，或其他已认证的 Google API 会话。
- `BING_WEBMASTER_API_KEY`：Bing Webmaster Tools 站点验证和 sitemap 提交。
- `CLARITY_PROJECT_ID`、`CLARITY_API_TOKEN`：已有 Clarity project 和项目级 Data Export API token。公开 Clarity MCP server 也使用已有 project token。
- `SITE_INTEGRATIONS_CONFIG`：可选的域名到仓库和集成元数据映射。

不要提交 `.env`、本地 Vercel 绑定、浏览器状态或生成的认证缓存。

缺少可选凭证时，不中断无关步骤。例如缺少 Clarity 或 Umami 凭证，只在最后把对应集成标记为 skipped 或 manual。

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
