---
name: jz-setup-analytics
version: "1.2.0"
description: "当公开站点已经在最终自定义域名上线，且用户要求接入 analytics、baseline metrics、Search Console、sitemap submission、IndexNow、Bing Webmaster Tools、Clarity 或 Sentry 时使用。触发语包括 set up GSC、connect analytics、do indexing onboarding、域名好了，接搜索和统计、接 Sentry、create Sentry project、get Sentry DSN。不要用于初始部署或 DNS cutover；先用 create-site 或 launch-domain。"
---

# 搜索与统计接入

用于最终域名已经可访问后，接入搜索、索引和统计。

这不是部署 skill，而是域名上线后的 onboarding：

1. Umami 或已配置的 web analytics
2. Google Search Console
3. IndexNow
4. Bing Webmaster Tools
5. Microsoft Clarity
6. Sentry（错误追踪：新建项目 + 获取 DSN + 配置到环境变量）

推荐顺序：

1. `create-site`
2. `launch-domain`
3. `setup-analytics`

## 前置条件

硬性前置条件：

1. 站点已经部署
2. 最终自定义域名已确定
3. 最终域名公网可访问

如果站点只在平台临时 URL 上，或自定义域名还在传播，停止并先用 `launch-domain`。

某个集成缺少凭据时，只阻塞该集成；继续处理其它集成，并在最后报告 skipped / blocked。

## 凭据

启动时从以下位置加载环境变量（先找到的优先）：

1. `~/.config/skills/jz-setup-analytics/.env` — 本机凭据（已 `.gitignore`）
2. skill 根目录 `.env` — 技能包内凭据

### Umami

- `UMAMI_BASE_URL` — Umami 地址（接受 origin 或 API base）
- `UMAMI_ADMIN_USERNAME` / `UMAMI_ADMIN_PASSWORD` — admin 登录凭据
- `UMAMI_SCRIPT_URL`（可选）— 前端脚本地址
- `UMAMI_API_KEY`（可选）— Umami Cloud fallback

### Google Search Console / Site Verification

- Google OAuth / ADC 已认证会话（`gcloud auth application-default login`）
- `GCP_QUOTA_PROJECT` — 已启用 Search Console + Site Verification API 的 GCP 项目。未设置时默认使用当前项目名（如 `clawsimple`、`auditmycareer`）

### Cloudflare（DNS TXT 验证记录）

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN` — 需 DNS 写权限（与 `jz-create-cf-token` 共享）

### Bing Webmaster Tools

- `BING_WEBMASTER_API_KEY` — 站点验证和 sitemap 提交

### Microsoft Clarity

- `CLARITY_ID` — Clarity project id（public）
- `CLARITY_TOKEN` — Data Export API token（不要打印或提交到前端）

### Sentry

- `SENTRY_API_TOKEN` — Sentry API token（需 `project:read`、`project:write`、`project:admin` 和 `org:read` 权限；从 [Sentry auth tokens](https://localfirstllc.sentry.io/settings/auth-tokens/) 创建）
- `SENTRY_ORG_SLUG`（可选）— 默认 `localfirstllc`；可通过 list projects 自动检测
- `SENTRY_TEAM_SLUG`（可选）— 默认与 org slug 相同；可通过 list projects 自动检测

### 站点集成映射（可选）

- `SITE_INTEGRATIONS_CONFIG` — 域名到仓库和集成元数据的 JSON 映射文件路径

## 输入

- 必填：最终公开域名，例如 `example.com`
- 可选：repo override，用于 site-to-repo 映射缺失时
- 可选：integration config path；默认使用 `$SITE_INTEGRATIONS_CONFIG`

## 目标

尽量完成最终域名的基础 onboarding：

- analytics script 已接入并 live，或说明跳过原因
- Search Console ownership 已验证，或说明 skipped / blocked
- 如果能编辑并部署 repo，`robots.txt` 和 `sitemap.xml` live
- 凭据允许时提交 sitemap
- 安装或确认 IndexNow 已存在
- Bing Webmaster Tools 已添加并验证，或说明 skipped / blocked
- Clarity 从共享 integration map 或 `CLARITY_ID` / `CLARITY_TOKEN` 验证，或说明跳过原因
- Sentry 项目已创建（以项目根目录名称为 slug），DSN 已获取并写入环境变量/secret，或说明跳过原因

## 核心规则

- 始终以最终自定义域名为准，不用平台临时 URL。
- 最终域名稳定前，不接 Search Console。
- 最终域名确定前，不生成或发布 IndexNow key。
- 首页 live 但缺 `sitemap.xml` 时，不要声称验证完成。
- IndexNow 不等于自动注册 Bing Webmaster Tools。
- 只读 metrics/reporting 工具不能用于 provision。
- 缺少凭据只阻塞对应集成。
- 一个集成不能跑时，记录 `skipped` 或 `blocked` 后继续。
- 需要代码改动但无法解析 repo 时，跳过 repo-editing，继续 API-only 或 live-site checks。
- 需要部署但缺少部署凭据时，不要声称本地改动已 live。
- Clarity project id 和 token 是项目级；优先共享 integration map，再回退到当前进程或 repo dotenv 中的 `CLARITY_ID` / `CLARITY_TOKEN`。
- Sentry API token 只能从 `SENTRY_API_TOKEN` 环境变量或凭据文件读取；不要从 repo dotenv 读取。

## 状态词

状态词定义见 repo 根目录 `docs/status-terms.md`。

## Repo 解析

优先读取项目 integration map。如果 `$SITE_INTEGRATIONS_CONFIG` 已设置：

```bash
cat "$SITE_INTEGRATIONS_CONFIG"
```

如果没有映射：

- 从当前 repo 判断 public domain
- 检查 package / framework 配置
- 只在必要时询问用户

## 集成流程

### 1. Live domain check

验证：

- `https://<domain>` 返回目标页面
- `robots.txt` 可访问或需要补
- `sitemap.xml` 可访问或需要补
- canonical / redirect 没有指向临时 host

### 2. Analytics

参考 `references/umami.md`。

确认 tracking script 是否在 live HTML 中出现。缺少凭据或 project mapping 时跳过并说明。

### 3. Google Search Console

参考 `references/search-console.md`。

只在最终域名稳定后处理。能自动验证就自动验证；需要用户完成 ownership 时，说明具体缺口。

### 4. Sitemap / robots

如果 repo 可编辑：

- 补齐或修复 `robots.txt`
- 补齐或修复 `sitemap.xml`
- 确保使用最终域名
- 部署后验证 live URL

### 5. IndexNow

参考 `references/indexnow.md`。如果 repo 还没有 IndexNow，可 handoff 到 `add-search-index`。

### 6. Bing Webmaster Tools

参考 `references/bing-webmaster.md`。不要把 IndexNow success 当作 Bing ownership success。

### 7. Clarity

参考 `references/clarity.md`。优先从共享配置或 env 获取 project id / token。

### 8. Sentry

参考 `references/sentry.md`。自动新建 Sentry 项目（slug 为当前 repo 根目录名），获取 DSN，按项目运行环境写入对应位置（Cloudflare Worker secret、Vercel env var、或 `.env`）。

不要交互式索要 Sentry API token；缺少 token 时报告 `skipped` 并继续。

## 完成汇报

最后按集成列出：

- `done`
- `skipped`
- `blocked`
- `needs deploy`
- `needs user action`

每项说明依据和下一步。不要把未验证的事项说成完成。
