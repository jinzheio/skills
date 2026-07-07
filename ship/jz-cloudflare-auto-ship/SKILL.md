---
name: jz-cloudflare-auto-ship
version: "1.0.0"
description: "当用户想把一个新网站或 Web app 从本地代码推进到 Cloudflare 上线，并顺手配置 GitHub、自动部署、正式域名、搜索/统计、转化埋点和 Auto PR 时使用。适用于 ship this site to Cloudflare、从代码到上线、Cloudflare auto ship、新站点发布全流程、上线后接 analytics 和 Auto PR。默认新站点发布到 Cloudflare，不处理 Vercel 迁移；迁移旧项目仍单独使用 jz-migrate-to-cf。"
---

# Cloudflare Auto Ship

用于编排新站点从本地代码到 Cloudflare 上线后的常见流程。

这个 skill 是总控，不重写部署、DNS、统计或 Auto PR 细节。它负责判断当前项目状态、选择阶段顺序、调用对应 skill、检查阶段门槛，并给出统一汇报。

默认路线：

```text
jz-create-cf-site -> jz-launch-domain -> jz-push-code -> jz-setup-analytics -> jz-track-conversion -> jz-set-auto-pr
```

其中 `jz-track-conversion` 和 `jz-set-auto-pr` 是按需阶段。用户没有要求转化埋点或 Auto PR 时，不默认实现。

## 范围

适用：

- 新站点或新 Web app 发布到 Cloudflare Workers / Workers Static Assets / Pages。
- 已有本地代码，需要创建或连接 GitHub repo。
- 已有 Cloudflare 临时 URL，需要绑定正式域名。
- 正式域名可访问后，接入统计、搜索索引、Sentry、Clarity。
- 已有 GitHub repo 后，配置 GitHub issue 触发的本机 Codex Auto PR runner。

不适用：

- 从 Vercel 迁移生产流量。使用 `jz-migrate-to-cf`。
- 只改 DNS。使用 `jz-launch-domain`。
- 只推送已有变更。使用 `jz-push-code`。
- 只接统计和搜索。使用 `jz-setup-analytics`。
- 只配置 Auto PR。使用 `jz-set-auto-pr`。

## 开始前

先读取：

- `references/preflight-checklist.md`
- `references/decision-matrix.md`
- `references/stage-gates.md`

如果当前仓库可运行 Node.js，可先执行：

```bash
node <skill-dir>/scripts/inspect-cloudflare-ship-state.mjs
```

脚本只做本地状态检查，不读取或输出 secret 值。脚本不可用时，用 reference 中的命令手动检查。

## 核心规则

- 新站点默认走 Cloudflare，不走 Vercel。
- 不复制其它 skill 的安全规则。进入具体阶段时，必须读取并遵守对应 skill。
- 不把“命令退出 0”当作完成。每阶段必须满足 `references/stage-gates.md` 的验收条件。
- 不静默 push 无关变更，不使用 `git add .`。
- 不输出 token、env 值、GitHub Secrets、API 响应里的敏感内容。
- 删除 DNS 记录、改 registrar、改生产域名、写 GitHub Secrets、创建 Cloudflare token 等动作，交给对应 skill 的确认规则处理。
- 如果阶段前置条件不满足，标记为 `skipped` 或 `blocked`，不要硬推进。

## 编排流程

### 1. 识别状态

收集：

- repo 路径、git 状态、remote、branch。
- package manager、build/check/test 命令。
- Cloudflare 配置：`wrangler.jsonc`、`wrangler.toml`、deploy script、bindings。
- GitHub Actions：生产部署 workflow、Auto PR workflow。
- 域名状态：临时 URL、正式域名、canonical host。
- 搜索和统计：robots、sitemap、analytics script、IndexNow、Sentry、Clarity。
- Auto PR 需求：是否需要 issue 自动处理、触发策略、self-hosted runner 和 dispatcher。

### 2. 选择路线

按 `references/decision-matrix.md` 判断需要哪些阶段。

常见路线：

- 只有本地代码：先 `jz-create-cf-site`。
- 已有 Cloudflare 部署但没有正式域名：先 `jz-launch-domain`。
- 已有正式域名但没统计：运行 `jz-setup-analytics`。
- 已有可部署 Cloudflare 项目但缺生产自动部署：运行 `jz-push-code`，由它检查并补 Cloudflare 自动部署 workflow。
- 需要 Auto PR：确认已有 GitHub repo 和本机 checkout 后，运行 `jz-set-auto-pr`。

如果用户要求“一次做完”，仍按阶段推进。高风险阶段由对应 skill 决定是否需要停下确认。

### 3. 执行阶段

每个阶段开始前，向用户说明：

- 本阶段调用哪个 skill。
- 本阶段完成条件。
- 本阶段可能跳过的分支。

阶段顺序：

1. **Cloudflare deploy**：使用 `jz-create-cf-site`。
2. **Domain**：用户给出正式域名时使用 `jz-launch-domain`。
3. **Production auto deploy / push**：使用 `jz-push-code`。
4. **Analytics and search**：正式域名可访问后使用 `jz-setup-analytics`。
5. **Conversion tracking**：用户要求转化漏斗或已有明确转化路径时使用 `jz-track-conversion`。
6. **Auto PR**：用户要求自动处理 issue 或自动提 PR 时使用 `jz-set-auto-pr`。

### 4. 中断与恢复

如果中间失败，不要重跑已完成阶段。按 `references/stage-gates.md` 复查当前状态，从第一个未满足验收条件的阶段恢复。

### 5. 完成汇报

读取 `references/report-template.md`，使用 `docs/status-terms.md` 状态词汇报：

- Cloudflare deploy
- GitHub repo / push
- production auto deploy
- domain / HTTPS / redirect
- analytics / search / Sentry / Clarity
- conversion events
- Auto PR
- skipped / blocked / manual 项

不要把没有 live 验证的结果写成 `done`。

## 相关 skill

- Cloudflare 发布：`jz-create-cf-site`
- Cloudflare token：`jz-create-cf-token`
- 域名绑定：`jz-launch-domain`
- 推送与 Cloudflare 自动部署：`jz-push-code`
- 搜索与统计：`jz-setup-analytics`
- IndexNow：`jz-add-search-index`
- 转化埋点：`jz-track-conversion`
- Auto PR：`jz-set-auto-pr`
- 旧项目迁移：`jz-migrate-to-cf`，只在用户明确要求迁移时使用
