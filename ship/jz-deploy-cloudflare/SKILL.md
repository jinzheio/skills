---
name: jz-deploy-cloudflare
description: "当用户想把本地网站或 Web app 完整发布到 Cloudflare 时使用，包括 deploy this site to Cloudflare、publish this local app on Cloudflare、wrangler deploy、create a GitHub repo and deploy to Cloudflare Workers、上线到 Cloudflare。支持 GitHub 不能关联 Cloudflare 时通过 Wrangler 直接发布。默认使用 Cloudflare 一级支持技术栈：Workers、Workers Static Assets、Wrangler、Workers Builds、Cloudflare 官方框架适配器和 Cloudflare 原生数据/存储产品。不要用于从 Vercel 迁移生产流量；迁移用 migrate-vercel-to-cloudflare。不要处理正式域名 cutover 或搜索/统计 onboarding；这些作为后续 handoff。"
---

# 发布本地站点到 Cloudflare

用于把本地 repo 发布成 Cloudflare 托管的站点。

这是 release workflow，不只是 `wrangler deploy`。任务是让 repo 可以稳定发布并正确连接：

1. 检查本地 repo 和 build 状态
2. 按需创建或连接 GitHub repo
3. 选择 Cloudflare 一级支持技术栈
4. 修复阻塞 Workers build 或 runtime 的问题
5. 配置 Wrangler、bindings、secrets 和生产环境变量
6. 本地验证 Workers runtime
7. 有意图地 commit 和 push
8. 创建或连接 Cloudflare Worker
9. 部署并验证 `workers.dev` 或用户指定的临时域名

默认使用 `wrangler deploy` 完成可验证部署。只有用户明确要求 Cloudflare 连接 GitHub / GitLab，或账号权限已确认可用时，才配置 Workers Builds。

如果用户说明 GitHub 账号不能关联 Cloudflare，只走 Wrangler 直发；不要要求 Cloudflare Git integration，也不要把 Workers Builds 列为待办。

如果用户还要正式域名和搜索/统计 onboarding，后续顺序是：

1. `setup-site-domain`
2. `setup-site-analytics`

如果用户是在把 Vercel 生产流量迁到 Cloudflare，改用 `migrate-vercel-to-cloudflare`。

## 输入

- 必填：本地 repo path，或当前就在目标 repo 中
- 必填：Cloudflare account id 或可用 `wrangler whoami`
- 可选：GitHub owner，例如 `<github-owner>`；只有需要创建或连接源码 repo 时必填
- 可选：repo / Worker name，默认当前目录名
- 可选：monorepo app root，例如 `apps/web`
- 可选：production env vars 来源：`.env.production`、`.env` 或其它路径
- 可选：repo visibility；默认 private，除非用户要求 public

如果用户未指定 repo name 或 Worker name，默认使用当前目录名。

## 必需工具和认证

任何 repo 或 deploy 改动前确认：

- `wrangler --version` 或项目内 `pnpm exec wrangler --version`
- `wrangler whoami` 或 `scripts/with-cloudflare-env.mjs ... wrangler whoami`

如果需要创建或连接 GitHub repo，再确认：

- `gh --version`
- `gh auth status`

如果缺少 `wrangler`，停止并说明缺哪个 CLI。只有当前任务需要 GitHub 时，缺少 `gh` 才阻塞。

如果缺少认证，先检查本项目 `.dev.vars`、`.env.local`、`.env` 等本地凭据。Cloudflare 操作默认使用项目自己的最小权限 `CLOUDFLARE_API_TOKEN`。

如果项目没有可用 token，使用 `create-cloudflare-token` skill：通过 `create-cloudflare-token` 本地配置读取 bootstrap token，为当前项目创建最小权限 token，或给已有项目 token 增加本次需要的权限。共享 token 只用于创建或更新项目 token，不得直接用于 `wrangler deploy`、资源创建、GitHub Secrets、Workers Builds 或其它项目操作。

不要输出 token 或 `.env` 值。

## 一级支持技术栈

默认选择 Cloudflare Workers，不默认选择 Vercel、Netlify、Docker、VPS、Workers Sites 或非官方适配层。

可接受路径：

- 静态站点、SPA：Workers Static Assets，`wrangler.jsonc` 的 `assets.directory` 指向构建产物。
- Vite + React/Vue/Svelte 等 SPA + API：Cloudflare Vite plugin 或 Workers Static Assets + Worker API。
- Astro、React Router、Next.js、Nuxt、SvelteKit 等框架：Cloudflare Workers 官方框架指南或官方/Cloudflare 维护适配器。
- Next.js：使用 Cloudflare OpenNext adapter，不使用 Vercel-only 功能作为生产依赖。
- 数据和存储：D1、R2、KV、Durable Objects、Queues、Vectorize、Hyperdrive、Workers AI、Secrets。
- 发布：Wrangler 直发是默认路径；Workers Builds 只在用户要求 Git 集成且账号可关联时配置。

不要为新项目使用 Workers Sites。不要把 Pages 作为默认承载面，除非项目已经明确以 Pages Git integration 为目标，或用户指定 Cloudflare Pages。

## 核心规则

- repo 检查优先用 `rg`。
- 不要用 `git add .`。
- 不要静默 push 无关本地改动。
- 不要使用 `reset --hard` 这类破坏性 git 命令。
- 默认创建 private GitHub repo，除非用户要求 public。
- 默认使用 Workers + Wrangler 配置，不写 Vercel 专属配置。
- monorepo 必须显式设置 Cloudflare project root / build working directory。
- lockfile 过期时先修复再发布。
- local build 或 Workers runtime 预览失败时先修复或报告 blocker，不要继续 release。
- 不要把域名 cutover、DNS 清理或 indexing 混进核心 repo-to-hosted-deploy 流程。
- Cloudflare deploy、resource create、secret sync、Workers Builds 和 GitHub Actions secrets 都必须使用项目最小权限 token。`create-cloudflare-token` 本地配置指定的共享 token 只能作为 bootstrap，用来创建或更新项目 token。

## 流程

### 1. 计划

阅读 `references/github-cloudflare-release.md`，执行其中 Repo Inspection commands，然后给出计划：

- GitHub owner 和 repo name，如果本次需要源码 repo
- repo visibility
- 当前 branch 和 dirty worktree
- package manager 与 build/check commands
- Cloudflare account 和 Worker name
- deploy root，尤其是 monorepo
- 选用的 Cloudflare 技术栈和理由
- 需要创建的 bindings / resources
- 需要同步的 production env vars / secrets
- 预期 commit / push / deploy 步骤
- 是否使用 Wrangler 直发，或是否需要 Workers Builds

### 2. 准备 repo

检查：

- 是否已经是 git repo
- remote 是否存在
- 当前 branch
- 未提交变更
- `.gitignore`
- lockfile 与 package manager
- build 是否可运行
- 是否已有 `wrangler.jsonc`、`wrangler.toml`、`open-next.config.ts`

如果不是 git repo，初始化并添加合适 `.gitignore`。

### 3. Cloudflare 适配

按项目类型选择最小改动：

- 已有 Wrangler 配置：审查并修正 `name`、`main`、`assets`、`compatibility_date`、bindings。
- 静态站点 / SPA：添加 Workers Static Assets 配置。
- Next.js：添加 Cloudflare OpenNext adapter、`open-next.config.ts`、Wrangler 配置和 scripts。
- 需要 API：用 Worker `fetch` handler 或框架路由，不引入 Node server。
- 需要数据库/对象存储/队列：创建或复用 Cloudflare 原生资源，把 binding 写入 Wrangler 配置。

详细命令见 `references/github-cloudflare-release.md`。

### 4. GitHub（可选）

用户需要源码 repo 时，创建或连接 GitHub repo：

- 默认 private
- 使用用户指定 owner
- remote 使用 SSH
- 不覆盖已有 remote，除非用户确认
- push 前确保 commit 只包含目标变更

### 5. Build 与修复

运行适用检查：

- lint / typecheck
- build
- Workers runtime preview

失败时只修复与发布直接相关的问题。不要做无关重构。

### 6. Cloudflare env / secrets

同步最低限度 production env vars。细节见 `references/env-sync.md`。

原则：

- secret 用 `wrangler secret put` 或 Cloudflare dashboard secret。
- 非 secret 变量写 Wrangler `vars` 或 Workers Builds 环境变量。
- Wrangler 和 Cloudflare API 操作用项目最小权限 token；缺失或权限不足时先用 `create-cloudflare-token` 创建或更新项目 token。
- 不输出 secret 值。
- `.env.local` 只能用于本机 CLI 注入，确认被 Git 忽略且未纳入 Git 管理。

### 7. Deploy

默认顺序：

1. `wrangler deploy`
2. GitHub Actions + 官方 Cloudflare Workers deploy action
3. Workers Builds GitHub / GitLab 集成

如果用户的 GitHub 账号不能关联 Cloudflare，固定使用第 1 项。不要把 Workers Builds 标记为 `manual`，除非用户仍要求后续人工连接。

部署验证见 `references/deploy-verify.md`。

### 8. 完成汇报

使用 `docs/status-terms.md` 里的状态词汇报：

- GitHub repo URL，如果本次创建或连接了 repo
- Cloudflare Worker / deployment URL
- 发布方式：Wrangler 直发、GitHub Actions 或 Workers Builds
- build/check/runtime preview 结果
- production env / secrets 同步范围
- 创建或复用的 Cloudflare resources
- 是否还有未提交变更
- 后续是否需要 `setup-site-domain` 或 `setup-site-analytics`

## 相关引用

- GitHub + Cloudflare release：`references/github-cloudflare-release.md`
- env 同步：`references/env-sync.md`
- deploy 验证：`references/deploy-verify.md`
