---
name: jz-push-code
version: "1.6.0"
description: "当用户要求验证并推送仓库时使用，包括 push this、发布代码、推送到远端。必须优先分派 worker subagent 在独立 context window 中执行验证（lint、test、build）、提交和推送流程。运行适用检查，确保目标变更已提交，然后 push。只有缺 workflow 时才读取自动部署 reference 并补齐。用 [skip deploy] 跳过部署。部署完成后再执行 IndexNow。后端仓库、私有工具、API-only 改动或没有公开 URL 的改动不要运行 IndexNow。当带有 force 参数时（如 push-code force），跳过所有确认，自动按功能拆分提交并直接 push。"
---

# 验证并推送代码

用于在推送前完成检查、提交和远端 push。

## Subagent 启动协议

触发本 skill 后，父 agent 必须优先分派一个 subagent 执行本 skill，以获得独立的 context window。

父 agent 只负责：

1. 创建或复用同一个 subagent ("worker")
1. 向 worker 传递仓库绝对路径、用户原始请求、本 skill 文件路径和当前确认状态
1. 等待 worker 返回确认问题、验证结果、push 结果、索引结果或 blocker
1. 将 worker 的确认问题转述给用户
1. 用户确认后，把确认消息发送给同一个 worker 继续执行
1. 根据 worker 结果向用户做最终汇报

worker subagent 的初始任务必须包含：

```text
你在 /absolute/path/to/repo 中执行 push-code skill。
先阅读仓库内 AGENTS.md 和 push-code/SKILL.md。
保持脏工作区现状，不要还原用户变更。
[CONFIRMATION_MODE]。
推送前确保目标变更已提交、适用检查通过、工作区干净。适用检查包括 lint、test、build。只有仓库有此命令时才执行。
如果是 Cloudflare 公开站点，推送前先确认 GitHub Actions 自动部署 workflow 存在；没有则读取 references/cloudflare-auto-deploy.md 并补齐。缺少 Cloudflare GitHub secrets 时，先找当前项目 `.dev.vars` / `.env.local` 里的项目最小权限 token；没有或权限不足时，再通过 `jz-create-cf-token` 本地配置读取共享 `CLOUDFLARE_ACCOUNT_ID` 和具备 Account API Tokens Write 权限的 bootstrap token，为当前项目创建专属最小权限 token，或给已有项目 token 增加必要权限，再写入 GitHub Secrets；只有共享凭据不可用、无法创建或更新项目 token、或权限验证失败时，才使用本机 `infra-credential-lookup` skill 继续查找。不要在 push 后询问本地 wrangler 发布。
本次 push 的 commit range 中任一 commit message 包含 `[skip deploy]` 时跳过自动部署，也不要执行 IndexNow 提交。
公开站点的公开页面改动按 references/post-push-indexing.md 执行 post-deploy IndexNow；Cloudflare 站点必须在 GitHub Actions 部署完成并验证后再提交 IndexNow。不适用时说明原因。
完成后报告验证、push、Cloudflare 发布、IndexNow 和 Search Console 结果。
```

父 agent 负责将上述 `[CONFIRMATION_MODE]` 替换为：
- force 模式（用户请求包含 `force`）：`"跳过所有确认。如果工作区有未提交变更，先自动按功能拆分并提交（参考 commit-code skill 的分组逻辑），然后直接验证并 push。不要询问用户确认。"`
- 正常模式：`"先请求确认，等待用户明确确认后再 lint、test、build、提交或 push。"`

如果当前环境没有 subagent 工具，才在父 agent 当前 context 中执行本流程，并在汇报中说明已降级为本地执行。

## 步骤

### 0. Force 模式

当用户请求包含 `force` 时（如 `push-code force`、`push this force`），启用 force 模式：

- 跳过步骤 1（请求确认），直接进入步骤 2。
- 如果工作区有未提交变更，先自动按功能拆分并提交（参考 commit-code skill 的分组逻辑：同一功能的文件放同一个 commit，untracked 文件放入归属功能的 commit，使用 Conventional Commits），然后再验证并 push。不要询问用户确认。
- 其余流程与正常模式一致。

### 1. 请求确认

**Force 模式下跳过此步骤。**

执行任何动作前，必须询问：

**”是否确认继续 lint、test、build 并推送代码？”**

必须等用户明确确认后继续。

### 2. 确认检查命令

推送前检查仓库：

- `package.json`
- lockfile：`pnpm-lock.yaml`、`package-lock.json`、`yarn.lock`、`bun.lockb`、`bun.lock`
- 如果 package scripts 不明确，检查 CI 配置

选择仓库已经使用的包管理器。

- 只有存在 lint script 或等价检查时才跑 lint
- 只有存在 build script 或等价检查时才跑 build
- 只有存在 test script（`test:ci`、`test` 或等价命令）时才跑 test
- 没有适用命令时标记为 `not applicable`

### 3. 判断是否需要索引

如果目标仓库是公开站点，且待推送变更影响公开页面、公开路由、sitemap、robots 或 canonical host 配置，则在最终 clean-tree 检查前阅读 `references/post-push-indexing.md`。

如果是后端、API-only、私有工具、内部项目，或改动无法映射到公开 URL，跳过 IndexNow 和 Search Console，并说明原因。

### 4. Cloudflare 自动部署检查

先做轻量判断。只有项目是 Cloudflare 公开站点时，才继续本节。

同时满足以下两类条件，才视为 Cloudflare 公开站点：

公开站点条件，满足任一项：

- 变更影响公开页面、公开路由、sitemap、robots 或 canonical host 配置
- public URL、sitemap、robots、canonical host 等配置可以解析到生产站点
- 项目文档明确说明这是公开 Web 站点

Cloudflare 托管条件，满足任一项：

- 仓库包含 `wrangler.toml`、`wrangler.json` 或 `wrangler.jsonc`
- `package.json` 中存在 `wrangler deploy`、`wrangler pages deploy`、`pages:deploy`、`deploy:cloudflare` 等发布命令
- 项目文档明确说明部署到 Cloudflare Workers 或 Cloudflare Pages
- public URL、sitemap、robots、canonical host 等配置指向 Cloudflare 托管站点

如果不是 Cloudflare 公开站点，不要读取 Cloudflare 自动部署 reference，继续后续验证和推送。

如果是 Cloudflare 公开站点，检查 `.github/workflows/*.yml` 和 `.github/workflows/*.yaml`。如果已经有能在 `push` 到生产分支后部署 Cloudflare 的 workflow，不要读取自动部署 reference，只记录 workflow 名称。

只有缺少自动部署 workflow 时，才读取 `references/cloudflare-auto-deploy.md`，按其中流程添加 workflow、检查 secrets，并把新增 workflow 放进本次提交。

如果 Cloudflare 自动部署所需的 GitHub secrets 缺失，先按 `references/cloudflare-auto-deploy.md` 的凭据约定处理：

- 先从当前项目 `.dev.vars`、`.env.local` 或其它本地 env 读取项目专属最小权限 `CLOUDFLARE_API_TOKEN` 和 `CLOUDFLARE_ACCOUNT_ID`。
- 如果项目 token 缺失或权限不足，通过 `jz-create-cf-token` 本地配置读取共享 `CLOUDFLARE_ACCOUNT_ID` 和具备 Account API Tokens Write 权限的 bootstrap token。
- 用 bootstrap token 创建当前项目专属的最小权限 `CLOUDFLARE_API_TOKEN`，或给已有项目 token 增加必要权限。
- 把项目 token 写入当前项目 `.dev.vars` 和 GitHub Secrets。

共享 bootstrap token 只用于创建或更新项目 token，不得写入当前项目 `.dev.vars` 或 GitHub Secrets，也不得用于项目部署、资源创建、Workers Builds 或 GitHub Actions。只报告凭据来源、创建/更新结果和权限边界，不输出 secret 值。项目 token 准备好后，必须用目标 Cloudflare API 验证权限，例如 Workers、D1 或 R2 项目调用。验证可用后，使用 `gh secret set` 写入缺失的 repo secrets。只有共享凭据不可用、无法创建或更新项目 token、项目 token 权限不足，或 GitHub repo secrets 无法写入时，才向用户报告 blocker 或索要最小所需凭据。

### 4.5. Cloudflare 账单安全检查

如果项目是 Cloudflare 站点，检查本次变更是否涉及新增或修改 Cloudflare 付费资源（Durable Objects、D1、R2、KV、Queues、Workers AI、Images、Browser Rendering）。

涉及付费资源时，读取 `references/cloudflare-billing-safety.md`，按其中检查流程逐项执行。

不涉及付费资源时跳过本节，继续后续验证。

### 5. 自动验证

- 跑适用的 lint / check
- 跑适用的 test
- 跑适用的 build
- 如果命令失败，不要 push
- 失败时阅读 `references/failure-policy.md`
- 只修复安全、窄范围的问题
- 重跑对应命令直到通过，或停止并报告 blocker

### 6. 保证工作区干净

运行 `git status`。

如果还有未提交变更：

- 创建有意义的 commit message
- 只 stage 目标文件，不要用 `git add .`，除非用户明确要求
- 提交后重新运行 `git status`
- 确认工作区干净

提交信息规则：

- 默认不要加 `[skip deploy]`
- 只有用户明确要求“只 push 不部署”“跳过部署”“不要发布线上”时，commit message 才加 `[skip deploy]`
- 如果本次 push 的 commit range 中任一 commit message 包含 `[skip deploy]`，后续不得执行 IndexNow；最终报告说明本次自动部署被跳过

### 7. 推送远端

当所有适用验证通过或标记为 `not applicable`，且工作区完全干净后，执行 `git push`。

### 8. 等待 Cloudflare 自动部署

如果项目是 Cloudflare 公开站点：

- 不要在本机运行 `wrangler pages deploy`、`wrangler deploy` 或其它本地发布命令
- push 后用 `gh run list` 按 head SHA、branch 和 workflow name 找到对应 workflow run
- 用 `gh run watch <run-id> --exit-status` 等待自动部署完成
- 部署失败时读取非敏感日志，报告失败步骤；不要执行 IndexNow
- 部署成功后，用 production URL、sitemap、robots 或项目已有健康检查验证线上已更新

如果本次 push 的 commit range 中任一 commit message 包含 `[skip deploy]`：

- 不等待部署
- 不执行 IndexNow
- 最终报告说明部署和索引都被 `[skip deploy]` 跳过

如果不是 Cloudflare 公开站点，报告跳过 Cloudflare 自动部署检查的原因。

### 9. 部署后 URL 收集

如果前面适用了 `references/post-push-indexing.md`，并且满足以下条件之一，才按其中 URL collection 流程执行：

- 项目不是 Cloudflare 站点
- Cloudflare 站点的 GitHub Actions 自动部署已经完成并通过验证

Cloudflare 公开站点没有完成发布验证时，不要收集或提交 IndexNow。

否则报告跳过索引和原因。

### 10. 部署后 IndexNow 提交

如果收集到了公开 URL，按 `references/post-push-indexing.md` 提交。

如果提交失败，报告失败和命令输出，不要声称成功。

### 11. Search Console Sitemap 检查

只有 sitemap 相关时才按 `references/post-push-indexing.md` 执行。

如果缺少 Google 凭据或站点 ownership，跳过并报告原因。

### 12. 完成汇报

报告：

- 验证和 push 已完成
- Cloudflare GitHub Actions 自动部署是否运行；如果跳过，说明原因；如果运行，报告 workflow run 和验证结果
- IndexNow 是否运行、提交 URL 数量和结果
- IndexNow 如果跳过，说明原因
- Search Console sitemap 处理结果或跳过原因
