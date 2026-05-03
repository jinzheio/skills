---
name: add-cloud-agent-collaborator
version: "1.1.0"
description: "当用户在本地/admin 侧要求为 OpenClaw、Hermes 或 cloud agent 增加 GitHub agent 合作者时使用。默认从本机未跟踪配置读取 owner 与 agent GitHub 账号，也支持用户临时指定账号。只设置 GitHub 权限边界：agent fork 可写、upstream 只读。不要用于 Vercel、Neon、服务器 clone、运行时登录、push、preview 或 PR 实作。"
---

# Add Cloud Agent Collaborator

用于在让 OpenClaw、Hermes 或其它 cloud agent 参与仓库开发前，增加 GitHub agent 合作者并准备权限边界。

## 本机账号配置

- 默认读取 `${ADD_CLOUD_AGENT_COLLABORATOR_CONFIG:-$HOME/.config/skills/add-cloud-agent-collaborator.env}`。
- 必填键：`OWNER_ACCOUNT`、`AGENT_GITHUB`、`AGENT_EMAIL`。
- 不要把本机配置文件提交到仓库，也不要把具体账号值写进这个 skill。

## 本机 GitHub 账号规则

- 普通仓库管理使用 `OWNER_ACCOUNT`。
- 只有用户明确要求操作 agent 账号或 cloud-agent 开发账户时，才使用 `AGENT_GITHUB`。
- 使用 `AGENT_GITHUB` 后，结束前必须切回 `OWNER_ACCOUNT`。

如果用户指定了其它 agent 邮箱或 GitHub 账号，全流程统一使用用户指定值。

安全模型：

```text
cloud agent -> agent fork -> preview deployment -> human review -> pull request -> upstream main
```

这个 skill 只准备 GitHub 权限边界，不创建 Vercel 项目、Neon 数据库，不 clone 服务器仓库，也不配置 OpenClaw / Hermes 运行时状态。

## 触发

用户类似这样表达时使用：

- “给这个 repo 增加一个开发者账户”
- “让 OpenClaw/Hermes 用 agent 账号参与开发”
- “给某个 agent account 设置 fork 权限”
- “准备一个 bot 开发账号，只能提 PR”

如果用户已经在 cloud agent 里要求它 clone、deploy、push 或创建 preview，不使用本 skill；那属于 `cloud-agent-project-dev-setup`。

## 输入

必填：

- upstream repo，例如 `OWNER/REPO`

可选：

- agent GitHub 账号，默认来自本机配置
- agent email，默认来自本机配置
- fork owner，默认等于 agent GitHub 账号

## 加载本机配置

流程开始时读取本机未跟踪配置：

```bash
CONFIG_FILE="${ADD_CLOUD_AGENT_COLLABORATOR_CONFIG:-$HOME/.config/skills/add-cloud-agent-collaborator.env}"
test -f "$CONFIG_FILE" && set -a && . "$CONFIG_FILE" && set +a

: "${OWNER_ACCOUNT:?Set OWNER_ACCOUNT in local config or the shell environment}"
: "${AGENT_GITHUB:?Set AGENT_GITHUB in local config or the shell environment}"
: "${AGENT_EMAIL:?Set AGENT_EMAIL in local config or the shell environment}"
```

如果配置缺失，询问用户 owner 账号和 agent 账号，然后只在当前 shell 中使用这些变量。不要把账号值写入 versioned skill。

## GitHub 最小权限

对每个 upstream repo：

1. 确认 upstream repo 和默认分支。
2. 在 agent account / fork owner 下创建或验证 fork。
3. 确认 agent account 对 upstream 至多是 read。
4. 确认 agent account 对自己的 fork 可写。
5. 如果 upstream 误给了 write/admin，移除该权限；需要时重新加 read-only。

命令：

```bash
UPSTREAM="OWNER/REPO"
REPO="${UPSTREAM#*/}"

gh auth switch --hostname github.com --user "$OWNER_ACCOUNT"
gh repo view "$UPSTREAM"
gh api "repos/$UPSTREAM/collaborators/$AGENT_GITHUB/permission"
```

期望：

- upstream permission：`read` 或没有 direct write/admin
- fork permission：owner/admin 或可写

只要 agent account 能 push upstream `main`，就不要继续 agent workflow。

## 双账号本地流程

本机可能同时登录 owner 和 agent 两个 GitHub 账号。保持 `OWNER_ACCOUNT` 为默认 active account。

检查 active account：

```bash
gh auth status --active
```

切换账号：

```bash
gh auth switch --hostname github.com --user "$AGENT_GITHUB"
gh auth switch --hostname github.com --user "$OWNER_ACCOUNT"
```

如果 agent account 没有登录，使用网页登录，并让用户用 `AGENT_GITHUB` 授权：

```bash
gh auth login --hostname github.com --web --scopes repo
```

选择 SSH；除非用户要求，不上传 SSH key；使用 CLI 显示的 device code 在浏览器授权。

私有 upstream repo 中，owner token 不能代替 agent account 接受邀请或创建个人 fork。使用这个顺序：

```bash
UPSTREAM="OWNER/REPO"
REPO="${UPSTREAM#*/}"

# Owner side: send read-only collaborator invite.
gh auth switch --hostname github.com --user "$OWNER_ACCOUNT"
gh api -X PUT "repos/$UPSTREAM/collaborators/$AGENT_GITHUB" -f permission=pull

# Agent side: accept invite and create fork.
gh auth switch --hostname github.com --user "$AGENT_GITHUB"
INVITE_ID="$(gh api user/repository_invitations --jq ".[] | select(.repository.full_name==\"$UPSTREAM\") | .id" | head -n 1)"
test -n "$INVITE_ID" && gh api -X PATCH "user/repository_invitations/$INVITE_ID"
gh repo view "$AGENT_GITHUB/$REPO" || gh repo fork "$UPSTREAM" --clone=false

# 从 agent 账号验证。
gh repo view "$UPSTREAM" --json nameWithOwner,defaultBranchRef,viewerPermission,viewerCanAdminister,isPrivate
gh repo view "$AGENT_GITHUB/$REPO" --json nameWithOwner,defaultBranchRef,viewerPermission,viewerCanAdminister,isPrivate

# Restore local default account.
gh auth switch --hostname github.com --user "$OWNER_ACCOUNT"
```

agent account 下的期望验证结果：

- upstream `viewerPermission`：`READ`
- upstream `viewerCanAdminister`：`false`
- fork `viewerPermission`：`ADMIN`
- fork `viewerCanAdminister`：`true`

## 交接给 Cloud Agent

GitHub 权限正确后，给 OpenClaw / Hermes agent 发送：

```text
本 repo 使用 cloud-agent-project-dev-setup。
Agent account: <agent email> / <agent github>
Upstream: OWNER/REPO
Fork: <agent github>/REPO
只 push 到你的 fork。不要 push upstream。
创建或连接你自己的 Vercel preview project 和 Neon preview DB。
在 cloud agent 服务器上使用 `/opt/clawsimple/Projects/<agent>/<repo>`。
只有我确认 preview 后，才创建 PR。
```

## 验证清单

- 已识别 upstream 默认分支
- agent fork 存在
- agent account 不能 push upstream
- agent account 可以 push fork
- GitHub CLI active account 已切回 `OWNER_ACCOUNT`
- handoff 包含 upstream、fork 和 agent account
