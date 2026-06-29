# GitHub + Cloudflare Release

## Repo Inspection commands

```bash
pwd
git status --short --branch
git remote -v
git branch --show-current
rg --files -g '!*node_modules*' -g '!*.png' -g '!*.jpg' -g '!*.jpeg' -g '!*.gif' -g '!*.webp' | sed -n '1,160p'
rg -n '"(scripts|dependencies|devDependencies|packageManager)"|wrangler|cloudflare|open-next|opennext|vite|next|astro|remix|react-router|svelte|nuxt|pages|vercel' package.json wrangler.* next.config.* astro.config.* vite.config.* open-next.config.* 2>/dev/null || true
```

检查 package manager：

```bash
test -f pnpm-lock.yaml && echo pnpm
test -f yarn.lock && echo yarn
test -f package-lock.json && echo npm
test -f bun.lockb -o -f bun.lock && echo bun
```

## Cloudflare 技术栈选择

优先顺序：

1. Workers + Workers Static Assets
2. Workers + 官方框架适配器
3. Wrangler 直发
4. GitHub Actions + 官方 Cloudflare Workers deploy action
5. Workers Builds，仅当用户要求 Git 集成且账号可关联
6. Cloudflare Pages，仅当用户指定或项目已有 Pages 约束

不使用：

- Workers Sites
- Vercel-only adapter
- Netlify-only adapter
- 自建 Node server / Docker / VPS
- 使用 `wrangler deploy` 直发，却声称已经建立 Cloudflare Git 集成

## 常见项目映射

### 静态站点或 SPA

添加 `wrangler.jsonc`：

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "<worker-name>",
  "compatibility_date": "<today>",
  "assets": {
    "directory": "./dist",
    "not_found_handling": "single-page-application"
  },
  "observability": {
    "enabled": true
  }
}
```

如果构建产物不是 `dist`，按项目实际输出目录填写。

### Vite SPA + API

优先使用 Cloudflare Vite plugin。若项目已有独立 API 约束，可用 Worker `fetch` handler 作为 API 入口，静态资源仍通过 `assets.directory`。

### Next.js

使用 Cloudflare OpenNext adapter：

```bash
<pm> add @opennextjs/cloudflare@latest
<pm> add -D wrangler@latest
```

`wrangler.jsonc`：

```jsonc
{
  "$schema": "./node_modules/wrangler/config-schema.json",
  "name": "<worker-name>",
  "main": ".open-next/worker.js",
  "compatibility_date": "<today>",
  "compatibility_flags": ["nodejs_compat"],
  "assets": {
    "directory": ".open-next/assets",
    "binding": "ASSETS"
  },
  "observability": {
    "enabled": true
  }
}
```

`open-next.config.ts`：

```ts
import { defineCloudflareConfig } from "@opennextjs/cloudflare";

export default defineCloudflareConfig();
```

`package.json` scripts：

```json
{
  "preview": "opennextjs-cloudflare build && opennextjs-cloudflare preview",
  "deploy": "opennextjs-cloudflare build && opennextjs-cloudflare deploy",
  "cf-typegen": "wrangler types --env-interface CloudflareEnv cloudflare-env.d.ts"
}
```

`compatibility_date` 使用执行当天日期。Next.js 需要 `nodejs_compat`，日期不得早于 `2024-09-23`。

### Astro / React Router / Nuxt / SvelteKit

按 Cloudflare Workers framework guide 使用对应官方适配器。不要猜配置；先读项目文件，确认当前框架版本和 adapter。

## Cloudflare resources

按需创建：

```bash
<pm> exec wrangler d1 list --json
<pm> exec wrangler d1 create <db-name>
<pm> exec wrangler d1 migrations apply <db-name> --remote
<pm> exec wrangler r2 bucket list
<pm> exec wrangler r2 bucket create <bucket-name>
<pm> exec wrangler queues list
<pm> exec wrangler queues create <queue-name>
<pm> exec wrangler vectorize list
<pm> exec wrangler vectorize create <index-name> --dimensions=<n> --metric=cosine
```

创建后把 binding 写回 `wrangler.jsonc`，并提交配置。不要把 resource id 写进无关文件。

## GitHub

如果没有 repo：

```bash
gh repo create <owner>/<repo> --private --source . --remote origin
```

如果已有 remote，确认 owner/repo 正确后继续。不要覆盖 remote，除非用户确认。

## Wrangler 直发

GitHub 账号不能关联 Cloudflare 时，使用 Wrangler 直发作为正式发布路径：

```bash
<pm> exec wrangler deploy
```

要求：

- `wrangler.jsonc` / `wrangler.toml` 已提交或准备提交。
- bindings 和 secrets 已在 Cloudflare 账户中创建。
- 本地 `.env.local` 只用于 CLI 凭据注入，并被 Git 忽略。
- 每次发布前运行项目 build/check 和 `wrangler deploy --dry-run`。
- 发布后用线上 URL 验证 HTTP、核心页面、静态资源和 API。

如果用户仍希望代码留档，可创建 GitHub repo，但不要尝试把 repo 关联到 Cloudflare。

## Workers Builds（可选）

Cloudflare Workers Builds 支持连接 GitHub/GitLab repo，并在 push 后自动 build 和 deploy。创建或连接时必须确保：

- Cloudflare dashboard 里的 Worker name 与 Wrangler 配置里的 `name` 一致。
- monorepo root / build working directory 指向目标 app。
- build command 使用项目 package manager。
- deploy command 最终执行 `wrangler deploy` 或框架 adapter deploy。
- 需要的 build env 和 runtime secret 已同步。

如果账号不能关联 Cloudflare，跳过 Workers Builds，不列为待办。只有用户要求后续人工连接时，才用 `manual` 汇报 dashboard 连接步骤。

## 本地验证

运行适用命令：

```bash
<pm> install
<pm> lint
<pm> typecheck
<pm> build
<pm> exec wrangler deploy --dry-run
<pm> exec wrangler dev --local
```

`wrangler dev` 是长进程，只在需要浏览器或 curl 验证时启动。结束前关闭进程。

## 部署

Wrangler 直发：

```bash
<pm> exec wrangler deploy
```

Next.js：

```bash
<pm> run deploy
```

部署输出必须记录 Worker name、deployment id/version id、`workers.dev` URL 或 custom domain。
