# Stage Gates

每个阶段完成后按这里验收。未满足时，不进入依赖它的后续阶段。

## Cloudflare Deploy

`done` 条件：

- build/check 已通过，或明确说明不适用。
- Cloudflare 返回 Worker / Pages deployment 信息。
- 临时 URL 或自定义域名 HTTPS 可访问。
- 首页核心内容或 title 符合目标站点。
- 静态资源返回 200。
- 有 API 时，至少验证一个只读 API 或 health endpoint。
- 有 D1/R2/KV/Queues/Vectorize 时，验证对应 binding 可访问。

调用 skill：`jz-deploy-cloudflare`。

## GitHub Repo And Push

`done` 条件：

- remote 指向目标 GitHub repo。
- 当前目标变更已提交。
- push 成功。
- 工作区没有未说明的剩余变更。

调用 skill：`jz-deploy-cloudflare` 或 `jz-push-code`。

## Production Auto Deploy

`done` 条件：

- `.github/workflows/` 中存在生产部署 workflow，或项目明确选择 Wrangler 直发且用户接受。
- GitHub Secrets 中存在所需 Cloudflare secrets。
- 最近一次目标分支 push 触发 workflow。
- workflow 成功。
- 生产 URL 验证通过。

调用 skill：`jz-push-code`。

## Domain

`done` 条件：

- canonical host 已确定。
- apex 和 `www` 的策略明确。
- HTTPS 可访问。
- HTTP 到 HTTPS 行为正确。
- canonical redirect 符合预期。
- 页面内容是目标站点。

调用 skill：`jz-setup-site-domain`。

## Analytics And Search

`done` 条件：

- 最终正式域名可访问。
- robots 和 sitemap live，或明确说明项目不需要 sitemap。
- Analytics script live，或因缺凭据标记 `skipped`。
- Search Console ownership 和 sitemap 按凭据能力处理。
- IndexNow key 和提交流程按项目状态处理。
- Clarity / Sentry 按凭据能力处理。

调用 skill：`jz-setup-site-analytics`。

## Conversion Tracking

`done` 条件：

- 事件命名和属性命名确定。
- 目标组件或流程已埋点。
- 浏览器 network 或统计后台确认事件到达。

调用 skill：`jz-setup-conversion-tracking`。

## Auto PR

`done` 条件：

- dispatcher 已安装或更新到 skill 模板版本。
- repo 到本机 checkout 的映射已写入本机配置。
- Auto PR workflow 存在，触发策略已说明。
- self-hosted runner online，且 workflow 的 `runs-on` label 能匹配它。
- 已用测试 issue 验证 Actions run、issue comment、`codex/*` branch 和 PR 创建。
- 如果没有真实 issue 验证，标记为 `partial`，说明只完成 dispatcher、YAML 和本机配置检查。

调用 skill：`jz-setup-auto-pr`。
