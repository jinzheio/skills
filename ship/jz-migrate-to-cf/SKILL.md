---
name: jz-migrate-to-cf
description: 将 Web 项目从 Vercel 迁移到 Cloudflare Workers、Pages 或 Cloudflare 原生托管。适用于用户要求迁移、发布、重新部署或把站点从 Vercel 移到 Cloudflare，尤其涉及自定义域名、Vercel GitHub 自动部署、Vercel 平台资源、vercel.json、Cloudflare DNS、Workers custom domains、D1、R2、Queues、Vectorize、Wrangler 或域名交接时。
---

# Vercel 到 Cloudflare 迁移

## 目标

把生产流量从 Vercel 迁到 Cloudflare，同时避免泄露密钥、误删 DNS 记录、遗漏 Vercel 平台能力，或让 Vercel 在下一次 GitHub push 后重新接管生产域名。

优先使用 CLI/API。只有 CLI/API 无法完成时，才使用浏览器自动化。

当操作 Vercel、GitHub 或 Cloudflare 需要 API token、登录态或权限时，先检查可用的本地凭据，再向用户索要：

1. 当前项目的 `.env`、`.env.local`、`.env.production`、`.env.development`、`.dev.vars`、`.vercel/` 等。
2. 团队约定的共享凭据文件或安全存储位置。
3. 用户级 CLI 或浏览器登录态，例如 `vercel whoami`、`gh auth status`、`wrangler whoami`。

检查 env 文件时只探测目标变量是否存在、来源路径、是否被 Git 忽略，以及是否纳入 Git 管理。不要读取、复制、输出或总结完整 env 文件内容。不要输出 token 值。只说明是否找到、来源路径或登录态，以及缺少的最小权限。

## 启动前必须先做

在执行任何会改变线上状态的操作前，先完成项目识别、迁移可行性检查和技术栈推荐。不要一上来创建 Cloudflare 资源、改 DNS、移除 Vercel alias、删除 Vercel project 或 push。

评估内容：

- 当前项目类型和现有框架。
- 当前项目是否能直接部署到 Cloudflare。
- 最少改动迁移是否合理，是否应该重新选择适合 Cloudflare 的技术栈。
- 是否使用了 Vercel 平台资源。
- 是否存在 Vercel 配置文件或项目设置会影响迁移。
- 域名当前由谁托管、Vercel 绑定在哪里、GitHub 自动部署是否仍会触发。

先基于当前项目给出初步技术栈推荐，再询问用户是否有会改变最优方案的约束。不要把问题问成阻塞式需求收集；如果已经能从代码判断项目类型，就先说明当前判断和推荐，再列出哪些约束会改变结论。至少确认：

- 是否必须保留当前框架。
- 是否必须保留 SSR、Middleware、API routes、Route Handlers、Server Actions、ISR、Image Optimization 等 Next.js 特性。
- 是否必须保留 i18n、多语言路由或 locale 检测。
- 是否接受只保留英文、移除多语言、去掉 SSR/中间件，或保留设计但换框架。
- 是否更重视最少改动上线，还是更重视后续维护成本和 Cloudflare 原生适配。

给技术栈建议后，再给迁移步骤。技术栈建议必须同时包含：

- 推荐方案：说明为什么最适合当前项目和用户约束。
- 备选方案：说明适用条件、改动量和风险。

必须向用户展示：

```text
我会按这些步骤执行：
1. 识别项目类型、现有框架和 Vercel 依赖。
2. 给出推荐方案和备选方案。
3. 询问是否有会影响技术栈选择的约束。
4. 检查 Vercel 平台资源和配置文件。
5. 移除 Vercel 生产域名绑定。
6. 创建或复用 Cloudflare 资源。
7. 清理指向 Vercel 的 DNS 记录。
8. 构建、迁移数据库并部署到 Cloudflare。
9. 验证线上域名。
10. 按需删除 Vercel 项目或断开 GitHub 集成。

请确认是否继续。
```

如果用户已经明确说“中间不要确认”“直接执行”“我确认”，可以继续非破坏性操作；否则先停下等确认。

这类一次性确认不能覆盖破坏性操作。任何删除 Vercel project、移除生产 alias、删除 DNS 记录、断开 GitHub 集成或清除线上资源的动作，都必须在执行前列出具体对象并再次等待用户确认。

## 迁移可行性检查

先按当前项目给出技术栈建议，再进入线上迁移动作。迁移评估不是只判断“能不能把当前框架跑起来”，还要判断“是否值得保留当前框架”。

先读这些文件，存在就重点检查：

```bash
rg --files | rg '(^|/)(astro\\.config\\.(js|mjs|ts)|vercel\\.json|next\\.config\\.(js|mjs|ts)|package\\.json|wrangler\\.(jsonc|toml)|\\.env\\.example|env\\.example)$'
rg -n 'Vercel|VERCEL|@vercel|next/image|ImageResponse|Edge Config|KV|Blob|Postgres|Analytics|Speed Insights|Cron|rewrites|redirects|headers|functions|regions|runtime|vercel|i18n|middleware|generateStaticParams|generateMetadata|server actions|use server|getStaticProps|getServerSideProps' .
```

重点判断：

- 项目类型：纯内容站、个人项目展示、文档站、营销页、博客、作品集、SaaS 应用、后台、带登录态应用、API 服务或混合应用。
- 现有框架：Next.js、Astro、Vite/React、SvelteKit、Nuxt、静态 HTML，或其他框架。
- 渲染方式：纯静态、SSG、SSR、ISR、边缘中间件、客户端应用。
- Next.js 是否依赖 Node-only API、ISR、Image Optimization、Middleware、Route Handlers、Server Actions、API routes、动态 metadata、动态 sitemap/robots。
- 是否使用 i18n、多语言路由、locale 检测、按语言生成 sitemap，或 `middleware` 做语言跳转。
- 是否使用 `@vercel/analytics`、`@vercel/speed-insights`、`@vercel/blob`、`@vercel/postgres`、Vercel KV、Edge Config。
- 是否依赖 Vercel Cron、Vercel rewrites/redirects/headers、环境变量、Build/Install/Output 设置。
- 是否使用 Vercel 域名、Vercel 自动 GitHub 部署、Preview URL、Protection、Skew Protection。
- 是否能用 Cloudflare Workers/Pages 直接承载，还是要改代码、换存储、换图片方案、换定时任务。

如果不能直接迁移，先列出改造项和风险，不要直接发布。

技术栈推荐细则见 `references/technical-stack.md`。需要在框架、SSR、i18n、Pages/Workers/OpenNext 之间做取舍时再读取；普通域名交接或单一路径部署不必加载。

## 安全规则

- 不输出 token、`.env` 值、含密钥的 API 响应或 `wrangler secret` 值。
- Vercel、GitHub、Cloudflare 需要 token 或登录态时，先检查可用的本地凭据；只探测目标变量是否存在和来源，不读取完整 env 文件；只有查不到或权限不足时才向用户索要。
- 删除 Vercel 项目、生产 alias、DNS 记录、GitHub 集成或线上资源前，必须先从 CLI/API 输出确认 project、domain、record id、record value 或 integration 名称，并再次等待用户确认。用户说过“直接执行”也不能跳过这次确认。
- 只删除目标 hostname 上指向 Vercel 的 Web 访问记录。保留 MX、SPF、DKIM、DMARC、Google verification 和无关 TXT。
- 在 Vercel 自定义域名或项目集成被处理前，不要 push。
- 本地部署凭据放 `.env.local`。确认 `.env.local` 被忽略且未纳入 Git 管理。
- 如果旧项目已纳入 Git 管理 `env.local`，用 `git rm --cached env.local` 从索引移除，只保留本地凭据。
- 使用 OpenNext for Cloudflare 时，绝不能用包含生产私密变量的完整 `.env` 直接构建或部署。OpenNext 会把构建时读取到的 env 写入 `.open-next/cloudflare/next-env.mjs`，并可能进入 Worker bundle。
- Vercel 生产 env 可以先同步到本地 `.env` 防止丢失，但 Cloudflare Worker 运行时变量必须写入 Worker vars/secrets；构建时只暴露 `NEXT_PUBLIC_*` 和确实必须在构建期使用的最小变量。
- 如果 SSG 构建必须读取私密变量，优先改代码使用公开只读凭据或受限 build-only 凭据；不要把生产 service role、支付密钥、邮件密钥、OIDC token 等带入 OpenNext 构建。
- OpenNext 部署后必须扫描 `.open-next` 产物，确认没有嵌入私密变量值或 Vercel 平台变量。扫描脚本只输出命中的变量名，不输出变量值。

## Cloudflare 账单防线

迁移到 Cloudflare 时，除了验证站点能访问，还要检查会产生按量账单的资源。默认把这一步当成上线前检查，不要等账单页出现费用后再排查。

执行这一节时先读取 `references/cloudflare-cost-guard.md`，并把其中的全局 AGENTS / CLAUDE / CODEX 部署规则作为约束。

优先检查这些资源：

- Workers：requests、CPU time、errors、subrequests。
- Durable Objects：duration、activeTime、cpuTime、WebSocket messages、rows read/written、storage read/write units。
- D1：rows read、rows written、storage。
- KV：read/write/delete/list operations、stored data。
- R2：class A/B operations、storage、egress 相关配置。
- Queues：operations、backlog、consumer retry。
- Vectorize、AI Gateway、Workers AI、Browser Rendering：按项目实际使用检查。

迁移或新建 Worker 前，执行工程检查：

- 如果 Durable Object 接 WebSocket，默认禁止 `server.accept()` / `ws.accept()`。必须使用 WebSocket Hibernation：`state.acceptWebSocket(server)`，并通过 `webSocketMessage`、`webSocketClose`、`webSocketError` 处理事件。
- 如果必须使用普通 WebSocket，先估算 `对象数 * 86400 秒 * 0.125 GB` 的单日 duration，并明确告诉用户费用上限风险。
- Worker 配置 CPU limit。它不能防 WebSocket duration，但能防 CPU runaway。
- 给 Worker 加 kill switch，例如 `WORKER_DISABLED=true` 或业务级 `RUNNER_NOTIFY_DISABLED=true` 时返回 503。
- 对定时任务、队列 consumer、Durable Object alarm 加最大批量、最大循环次数和错误退避。
- 避免在请求路径里无上限写 KV、D1、R2 或队列消息。

上线前提醒用户设置 Cloudflare 原生告警：

```text
Manage Account > Billing > Billable Usage > Create budget alert
建议至少设置：$1、$5、$10 三档。
```

同时说明限制：

- Budget alert 只发邮件，不会暂停服务。
- Usage notification 覆盖范围按产品而定，不能替代自建监控。
- Cloudflare 没有通用硬性花费上限，不能只靠账单页。

如果项目会长期运行 Cloudflare 付费资源，建议加一个本地或线上监控脚本。默认每 1 小时查询 Cloudflare GraphQL Analytics API，记录并告警：

```text
Durable Objects duration > 500 GB-s / hour       warning
Durable Objects duration > 2,000 GB-s / hour     critical
Durable Objects duration > 5,000 GB-s / day      critical
账期累计 Durable Objects duration > 100,000 GB-s warning
账期累计 Durable Objects duration > 300,000 GB-s critical
Workers errors > 0 且连续两次出现                     warning
Workers requests 或 KV/D1/R2/Queues 操作量突增          warning
```

可用 GraphQL dataset：

- `workersInvocationsAdaptive`
- `durableObjectsPeriodicGroups`
- `durableObjectsInvocationsAdaptiveGroups`
- `durableObjectsStorageGroups`
- `durableObjectsSubrequestsAdaptiveGroups`

如果当前项目没有监控页面，至少在交付时给出一条可重复执行的查询命令或脚本路径，并提醒用户第一次部署后 30 分钟内复查 Durable Objects duration。

## 流程

### 1. 识别当前状态

如果 Vercel CLI 未登录或权限不足，先查找 `VERCEL_TOKEN`、`.vercel/` project 信息或可用 CLI 登录态。查找 token 时只探测变量是否存在，不读取完整 env 文件。找到 token 时在单条命令的环境变量中使用，不写入仓库，不输出值。

运行：

```bash
git remote -v
git branch --show-current
git status --short --branch
for f in .env .env.local .env.production .env.development .dev.vars; do test -f "$f" && awk -F= -v file="$f" '/^(VERCEL_TOKEN|CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID|GITHUB_TOKEN)=/{print file ":" $1}' "$f"; done
for f in .env .env.local .env.production .env.development .dev.vars; do test -f "$f" && git check-ignore -q "$f" && echo "$f ignored" || true; done
for f in .env .env.local .env.production .env.development .dev.vars; do test -f "$f" && git ls-files --error-unmatch "$f" >/dev/null 2>&1 && echo "$f tracked" || true; done
vercel whoami
gh auth status
vercel teams ls
vercel projects ls --scope <scope>
vercel alias ls --scope <scope> --limit 100
```

找出：

- 旧 Vercel project 所在 scope。
- Vercel project 名称。
- 自定义域名 alias，例如 `example.com` 和 `www.example.com`。
- 用户是要删除 Vercel project，还是只移除 alias / 断开 GitHub。

### 2. 准备 Cloudflare 凭据

先查找 Cloudflare 凭据。优先使用当前项目 env；没有时检查团队约定的共享凭据文件或安全存储位置；再检查 `wrangler whoami` 或用户级配置。

查找 env 时只输出变量名和来源文件，不输出值，不读取完整文件到对话上下文。

Cloudflare token 权限细则见 `references/permissions.md`。遇到权限报错或需要创建 D1、R2、Queues、Vectorize、Workers routes/custom domains 时再读取。

可识别的变量：

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

如果需要把凭据给 Wrangler 使用，放到当前项目 `.env.local` 或在单条命令环境变量中注入。不要输出值。只验证变量名、数量、ignore 状态和 tracked 状态：

`.env.local` 使用简单 `KEY=value` 格式。不要使用 `export KEY=value` 或多行值。

```bash
awk -F= '/^(CLOUDFLARE_API_TOKEN|CLOUDFLARE_ACCOUNT_ID)=/{print $1; c++} END{print "count=" c+0}' .env.local
git check-ignore -v .env.local
git ls-files --error-unmatch .env.local >/dev/null 2>&1 && echo ".env.local tracked" || echo ".env.local untracked"
```

用 `scripts/with-cloudflare-env.mjs` 给 Wrangler 注入 `.env.local`：

```bash
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler whoami
```

如果项目需要长期复用，把这个脚本复制到仓库内。

### 3. 处理 Vercel 生产域名

如果移除 alias 或删除 project 需要 token，先查找 `VERCEL_TOKEN` 或可用 Vercel CLI 登录态。确认 token 所属 scope 有目标 project 权限后再执行。

执行移除生产 alias 或删除 project 前，必须先列出将删除的具体对象，并等待用户再次确认。不要因为用户已经说过“直接执行”而跳过。

确认文本使用：

```text
将删除以下 Vercel 对象：
- project: <project-name>
- alias: <domain>
- alias: <www-domain>

请确认是否删除这些对象。
```

移除生产 alias：

```bash
vercel alias remove example.com --scope <scope> --yes
vercel alias remove www.example.com --scope <scope> --yes
vercel alias ls --scope <scope> --limit 100 | rg 'example\.com|www\.example\.com' || true
```

如果用户要求停止 GitHub 触发的 Vercel 自动部署，删除 project：

```bash
printf 'y\n' | vercel project remove <project-name> --scope <scope>
vercel project inspect <project-name> --scope <scope>
```

成功信号：

```text
There is no project for "<project-name>"
```

### 4. 创建或复用 Cloudflare 资源

如果创建 D1、R2、Queues、Vectorize、Workers route 或 Pages project 需要权限，先查找 Cloudflare token。确认 token 至少有目标账户和目标 zone 的读写权限；权限不足时只向用户索要缺失权限。

Workers 内容型应用常用资源：

```bash
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler d1 list --json
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler d1 create <db-name>
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler r2 bucket list
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler r2 bucket create <bucket-name>
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler queues list
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler queues create <queue-name>
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler vectorize list
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler vectorize create <index-name> --dimensions=<n> --metric=cosine
```

把真实 D1 `database_id` 写回 `wrangler.jsonc`。

Workers 自定义域名配置：

```jsonc
"routes": [
  { "pattern": "example.com", "custom_domain": true },
  { "pattern": "www.example.com", "custom_domain": true }
]
```

### 5. 清理旧 Vercel DNS 记录

如果需要通过 Cloudflare API 读写 DNS，先查找 `CLOUDFLARE_API_TOKEN` 和 `CLOUDFLARE_ACCOUNT_ID`。如果 token 缺少 Zone read、DNS edit 或 Workers Routes edit，只说明缺少的权限，不要求用户重新提供无关凭据。

部署 custom domain 前，列出 Cloudflare DNS：

```bash
CF_CURL_CONFIG="$(mktemp)"
trap 'rm -f "$CF_CURL_CONFIG"' EXIT
chmod 600 "$CF_CURL_CONFIG"
printf 'header = "Authorization: Bearer %s"\n' "$CLOUDFLARE_API_TOKEN" > "$CF_CURL_CONFIG"

curl -sS --config "$CF_CURL_CONFIG" \
  "https://api.cloudflare.com/client/v4/zones?name=example.com"
```

只删除旧 Web 记录：

- `A example.com -> Vercel IP`
- `CNAME www.example.com -> *.vercel-dns-*`
- 服务旧 Vercel app 的 `AAAA` 或 `CNAME`

删除 DNS 记录前，必须列出每条记录的 `id`、`name`、`type`、`content`、`proxied` 和删除原因，并等待用户再次确认。不要因为用户已经说过“直接执行”而跳过。

确认文本使用：

```text
将删除以下 Cloudflare DNS 记录：
- <id> <type> <name> -> <content> proxied=<true|false>，原因：指向旧 Vercel 服务

请确认是否删除这些 DNS 记录。
```

保留：

- MX
- TXT SPF/DKIM/DMARC
- 站点验证 TXT
- 无关子域名

如果 Wrangler 报：

```text
Hostname '<domain>' already has externally managed DNS records
```

删除冲突的 A/AAAA/CNAME 后重新部署。

为 Cloudflare Pages 或 Workers 绑定自定义域名时，DNS 记录优先使用 Cloudflare `proxied` 模式：

- Pages 常用 `CNAME example.com -> <project>.pages.dev` 和 `CNAME www.example.com -> <project>.pages.dev`，默认设为 `proxied: true`。
- Workers routes/custom domains 默认走 Cloudflare 代理，不要改成 DNS only。
- 如果 Pages custom domain 验证报 `CNAME record not set` 或长期停在 pending，可临时把目标 CNAME 改为 DNS only，让 Pages 看到真实 CNAME。
- Pages domain 进入 `active` 后，再把 CNAME 切回 `proxied: true`，并重新验证正式域名可达。

### 6. 构建、迁移、部署

如果部署由 GitHub 集成触发，先检查 `gh auth status` 或 `GITHUB_TOKEN` 是否可用于查看/调整仓库集成。不要在 Vercel 自定义域名或项目集成处理完成前 push。

#### 运行时变量专题

如果项目使用 OpenNext for Cloudflare，读取 `references/opennext-env.md`。核心规则：构建期只给 `NEXT_PUBLIC_*` 和必要 build-only 变量；运行时私密变量写入 Worker vars/secrets；部署使用 `--keep-vars` 或等价方式；部署前扫描 `.open-next` 产物。

如果项目使用 `wrangler pages deploy <dist>` 且包含 Pages Functions，读取 `references/pages-direct-upload-functions.md`。核心规则：先验证真实 API route 的 `context.env`；只有 Direct Upload Functions 读不到已配置变量时，才使用临时 `[vars]` 桥接。

生产前运行项目检查：

```bash
pnpm lint
pnpm typecheck
pnpm build
```

应用远端迁移：

```bash
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler d1 migrations apply <db-name> --remote
```

部署：

```bash
# OpenNext for Cloudflare
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec opennextjs-cloudflare deploy -- --keep-vars

# 普通 Workers 项目
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler deploy
```

确认 Wrangler 输出包含：

```text
Deployed <worker> triggers
  example.com (custom domain)
  www.example.com (custom domain)
```

### 7. 验证生产

生产验证以正式域名 HTTPS 可达为准，不要只看本地 DNS 解析结果。本地 DNS 记录可能被缓存或污染；如果普通 `curl` 因本地解析失败，但 Cloudflare 权威 DNS 已返回边缘 IP，可用 `curl --resolve` 指定 IP，同时保持 Host/SNI 为正式域名。

运行：

```bash
curl -sSIL --max-time 20 https://example.com
curl -sSIL --max-time 20 https://www.example.com
curl -sSL --max-time 20 https://example.com | rg -o '<title>[^<]+'
curl -sS --max-time 20 https://example.com/robots.txt
curl -sS --max-time 20 https://example.com/sitemap.xml | sed -n '1,20p'
```

如果本地解析异常，先取 Cloudflare 权威解析结果，再用 `--resolve` 验证访问：

```bash
dig @1.1.1.1 example.com A +short
curl -sSIL --max-time 20 --resolve example.com:443:<edge-ip> https://example.com/
curl -sSL --max-time 20 --resolve example.com:443:<edge-ip> https://example.com | rg -o '<title>[^<]+'
```

验证 Cloudflare domain 状态和 DNS 记录：

```bash
CF_CURL_CONFIG="$(mktemp)"
trap 'rm -f "$CF_CURL_CONFIG"' EXIT
chmod 600 "$CF_CURL_CONFIG"
printf 'header = "Authorization: Bearer %s"\n' "$CLOUDFLARE_API_TOKEN" > "$CF_CURL_CONFIG"

# Pages custom domains 应为 active；DNS 记录优先保持 proxied。
curl -sS --config "$CF_CURL_CONFIG" \
  "https://api.cloudflare.com/client/v4/accounts/<account-id>/pages/projects/<project-name>/domains"

curl -sS --config "$CF_CURL_CONFIG" \
  "https://api.cloudflare.com/client/v4/zones/<zone-id>/dns_records?name=example.com"
```

验证 D1：

```bash
node <skill-dir>/scripts/with-cloudflare-env.mjs pnpm exec wrangler d1 execute <db-name> --remote --command "select name from sqlite_master where type='table' order by name;"
```

复查 Vercel：

```bash
vercel project inspect <project-name> --scope <scope>
vercel alias ls --scope <scope> --limit 100 | rg 'example\.com|www\.example\.com' || true
```

## 常见失败

- `--env-file` 后仍 `Not logged in`：Wrangler 的认证并不总是读取 `--env-file`。使用 `scripts/with-cloudflare-env.mjs`。
- Vectorize 返回 `Authentication error [code: 10000]`：给 Cloudflare token 增加 Vectorize 权限。
- `/workers/routes` 或 `/domains/records` 返回认证错误：给目标 zone 增加 Workers Routes edit 和 Zone read。
- `externally managed DNS records`：删除目标 hostname 上旧 A/AAAA/CNAME。
- OpenNext 部署后 Worker 还能读到 `.env` 私密变量：说明构建时完整 `.env` 被嵌入了 `.open-next/cloudflare/next-env.mjs` 或 Worker bundle。改用只含 `NEXT_PUBLIC_*` 的安全构建脚本，runtime secrets 用 Cloudflare Worker secrets，并用 `--keep-vars` 部署。
- Pages custom domain 报 `CNAME record not set`：临时改成 DNS only，active 后切回 proxied 并验证 HTTPS。
- 本地 `dig` 或普通 `curl` 显示域名不可解析：不要只按本地 DNS 判断；用权威解析或 `curl --resolve` 直接验证域名 HTTPS 可达。
- `www` 刚部署后 TLS 失败：等待并重试，custom domain 证书和 DNS 可能有短暂延迟。

## 最终汇报

汇报：

- Vercel alias 已移除，或 project 已删除。
- Cloudflare 资源创建/复用情况。
- Worker deployment version id。
- 生产 URL 和 HTTP 状态。
- 已运行的验证命令。
- OpenNext 产物扫描结果，例如 `embedded_sensitive_keys=none`。
- 剩余风险，例如缺少模型/支付 secret、项目代码仍依赖 Vercel 平台能力、尚未 push。
