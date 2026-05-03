---
name: push-code
version: "1.1.0"
description: "当用户要求验证并推送仓库时使用，包括 push this、发布代码、推送到远端。运行适用检查，确保目标变更已提交，然后 push。公开站点如果改动了公开页面，还要执行 post-push IndexNow URL 提交。后端仓库、私有工具、API-only 改动或没有公开 URL 的改动不要运行 IndexNow。"
---

# 验证并推送代码

用于在推送前完成检查、提交和远端 push。

## 步骤

### 1. 请求确认

执行任何动作前，必须询问：

**“是否确认继续 lint、build 并推送代码？”**

必须等用户明确确认后继续。

### 2. 确认检查命令

推送前检查仓库：

- `package.json`
- lockfile：`pnpm-lock.yaml`、`package-lock.json`、`yarn.lock`、`bun.lockb`、`bun.lock`
- 如果 package scripts 不明确，检查 CI 配置

选择仓库已经使用的包管理器。

- 只有存在 lint script 或等价检查时才跑 lint
- 只有存在 build script 或等价检查时才跑 build
- 没有适用命令时标记为 `not applicable`

### 3. 判断是否需要索引

如果目标仓库是公开站点，且待推送变更影响公开页面、公开路由、sitemap、robots 或 canonical host 配置，则在最终 clean-tree 检查前阅读 `references/post-push-indexing.md`。

如果是后端、API-only、私有工具、内部项目，或改动无法映射到公开 URL，跳过 IndexNow 和 Search Console，并说明原因。

### 4. 自动验证

- 跑适用的 lint / check
- 跑适用的 build
- 如果命令失败，不要 push
- 失败时阅读 `references/failure-policy.md`
- 只修复安全、窄范围的问题
- 重跑对应命令直到通过，或停止并报告 blocker

### 5. 保证工作区干净

运行 `git status`。

如果还有未提交变更：

- 创建有意义的 commit message
- 只 stage 目标文件，不要用 `git add .`，除非用户明确要求
- 提交后重新运行 `git status`
- 确认工作区干净

### 6. 推送远端

当所有适用验证通过或标记为 `not applicable`，且工作区完全干净后，执行 `git push`。

### 7. Push 后 URL 收集

如果前面适用了 `references/post-push-indexing.md`，按其中 URL collection 流程执行。

否则报告跳过索引和原因。

### 8. Push 后 IndexNow 提交

如果收集到了公开 URL，按 `references/post-push-indexing.md` 提交。

如果提交失败，报告失败和命令输出，不要声称成功。

### 9. Search Console Sitemap 检查

只有 sitemap 相关时才按 `references/post-push-indexing.md` 执行。

如果缺少 Google 凭据或站点 ownership，跳过并报告原因。

### 10. 完成汇报

报告：

- 验证和 push 已完成
- IndexNow 是否运行、提交 URL 数量和结果
- IndexNow 如果跳过，说明原因
- Search Console sitemap 处理结果或跳过原因
