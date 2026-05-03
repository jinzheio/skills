---
name: upstart-site
version: "1.1.0"
description: "当用户想把本地网站或 Web app 完整发布上线时使用，包括 deploy this site、publish this local app、create a GitHub repo and deploy to Vercel、上线到 Vercel。创建或连接 GitHub，验证 build，push，连接 Vercel，同步最低限度生产环境变量，并验证 GitHub 触发的部署。不要处理自定义域名 cutover 或搜索/统计 onboarding；这些作为后续 handoff。"
---

# 发布本地站点

用于把本地 repo 发布成可托管的站点。

这是 release workflow，不只是 deploy command。任务是让 repo 可以稳定发布并正确连接：

1. 检查本地 repo 和 build 状态
2. 创建或连接 GitHub repo
3. 修复阻塞 CI 或 Vercel build 的问题
4. 有意图地 commit 和 push
5. 创建或连接 Vercel project
6. 连接 Vercel 和 GitHub
7. monorepo 时设置正确 root directory
8. 同步最低限度 production env vars
9. 触发并验证 GitHub-based production deployment

除非用户明确要求 local-source deployment，不要把本地 `vercel --prod` 当作完成。默认使用 GitHub-connected deploy。

如果用户还要正式域名和搜索/统计 onboarding，后续顺序是：

1. `new-domain-launch`
2. `index-onboarding`

如果用户还要最终域名的入站邮件转发，域名进入 Cloudflare 后交给 `new-domain-launch`。这不阻塞核心发布流程。

## 输入

- 必填：本地 repo path，或当前就在目标 repo 中
- 必填：GitHub owner，例如 `<github-owner>`
- 必填：Vercel team / scope，例如 `my-team`
- 可选：repo / project name，默认当前目录名
- 可选：monorepo app root，例如 `app`
- 可选：production env vars 来源：`.env.production`、`.env` 或其它路径
- 可选：repo visibility；默认 private，除非用户要求 public

如果用户未指定 repo name 或 Vercel project name，默认使用当前目录名。

## 必需工具和认证

任何 repo 或 deploy 改动前确认：

- `gh --version`
- `gh auth status`
- `vercel --version`
- `vercel whoami`

如果缺少 `gh` 或 `vercel`，停止并说明缺哪个 CLI。

如果缺少认证，停止并让用户先登录。

## 核心规则

- repo 检查优先用 `rg`。
- 不要用 `git add .`。
- 不要静默 push 无关本地改动。
- 不要使用 `reset --hard` 这类破坏性 git 命令。
- 默认创建 private GitHub repo，除非用户要求 public。
- 默认使用 GitHub-triggered Vercel deploy。
- monorepo 必须显式设置 Vercel root directory。
- lockfile 过期时先修复再发布。
- local build 失败时先修复或报告 blocker，不要继续 release。
- 不要把域名 cutover 或 indexing 混进核心 repo-to-hosted-deploy 流程。

## 流程

### 1. 计划

阅读 `references/github-vercel-release.md`，执行其中 Repo Inspection commands，然后给出计划：

- GitHub owner 和 repo name
- repo visibility
- 当前 branch 和 dirty worktree
- package manager 与 build/check commands
- Vercel team/scope 和 project name
- deploy root，尤其是 monorepo
- 需要同步的 production env vars
- 预期 commit / push / deploy 步骤

### 2. 准备 repo

检查：

- 是否已经是 git repo
- remote 是否存在
- 当前 branch
- 未提交变更
- `.gitignore`
- lockfile 与 package manager
- build 是否可运行

如果不是 git repo，初始化并添加合适 `.gitignore`。Next.js 项目可参考 `init-nextjs-git`。

### 3. GitHub

创建或连接 GitHub repo：

- 默认 private
- 使用用户指定 owner
- remote 使用 SSH
- 不覆盖已有 remote，除非用户确认
- push 前确保 commit 只包含目标变更

### 4. Build 与修复

运行适用检查：

- lint / typecheck
- build

失败时只修复与发布直接相关的问题。不要做无关重构。

### 5. Vercel

创建或连接 project：

- 使用用户指定 team / scope
- monorepo 设置 root directory
- 连接 GitHub repo
- 同步最低限度 production env vars
- 不把本地临时变量或 secret 打印出来

环境变量细节见 `references/env-sync.md`。

### 6. GitHub-triggered deploy

push 后让 Vercel 通过 GitHub 触发部署。不要用本地 deploy 伪装成 GitHub-connected deploy。

部署验证见 `references/deploy-verify.md`。

### 7. 完成汇报

报告：

- GitHub repo URL
- Vercel project / deployment URL
- build/check 结果
- production env 同步范围
- 是否还有未提交变更
- 后续是否需要 `new-domain-launch` 或 `index-onboarding`

## 相关引用

- GitHub + Vercel release：`references/github-vercel-release.md`
- env 同步：`references/env-sync.md`
- deploy 验证：`references/deploy-verify.md`
