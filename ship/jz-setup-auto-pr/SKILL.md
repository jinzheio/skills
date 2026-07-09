---
name: jz-setup-auto-pr
description: "把 GitHub repo 接入本机 Auto PR runner。适用于用户要求为新项目配置 issue 触发的 Auto PR、self-hosted runner workflow、repo 到本机 checkout 映射、dispatcher 配置、Codex / Claude Code agent 和测试 issue。触发词包括 auto PR、自动提 PR、issue auto PR、self-hosted runner、Codex runner、Claude Code runner、GitHub issue trigger、扩展到新 repo。"
---

# GitHub Issue Triggered Auto PR

把已有 GitHub repo 接入本机 Auto PR runner。

现在的默认流程是：

1. GitHub issue 触发 workflow。
2. GitHub Actions 把 job 派给已注册的 self-hosted runner。
3. runner 执行本机 dispatcher。
4. dispatcher 根据 repo 映射找到本机 checkout。
5. dispatcher 创建独立 worktree 和 agent 对应的 auto-pr branch。
6. 配置的本地 Agent CLI 在 worktree 里处理 issue、验证、commit、push、创建 PR。
7. dispatcher 把结果评论回 issue。

这个 skill 不负责 Cloudflare preview。PR preview、生产部署、Worker/Pages 清理交给部署相关 skill 或项目已有 workflow。

## 先确认

开始前确认这些信息：

- GitHub repo：`<owner>/<repo>`。
- base branch：通常是 `main`。
- 本机 checkout：用户机器上已经 clone 的目标 repo。
- dispatcher 路径：默认 `<home-dir>/.local/bin/jz-auto-pr-dispatch`，可用 `AUTO_PR_DISPATCH_PATH` 覆盖。
- repo 映射配置：例如 `<auto-pr-config-dir>/repos.json`。
- GitHub owner：从本机未跟踪配置 `<auto-pr-config-dir>/allowed-owner` 或 `AUTO_PR_ALLOWED_OWNER` 读取。
- self-hosted runner label：至少包含 `self-hosted` 和 `auto-pr`。现有 runner 如果只有 `codex` 标签也可以继续用；Agent 选择由 dispatcher 配置决定，不由 workflow step 名决定。
- 本地 Agent：默认 `codex`；可通过 `AUTO_PR_AGENT` 或 `<auto-pr-config-dir>/config.yml` 的 `agent` 字段设置为 `codex` 或 `claude-code`。
- 触发策略：
  - 默认：新 issue 和 reopened issue 直接触发。
  - 评论 `/auto-pr` 可用于手动重跑。
- PR 创建身份：优先使用 dispatcher 注入的本机 token，不要求打开 org 级 “Allow GitHub Actions to create and approve pull requests”。

如果用户只是问机制，先解释，不改文件。如果用户要求配置，直接改目标 repo 和本机配置。

## 配置位置

skill 文档中的路径都用占位符。实际路径从当前机器、已有 dispatcher 或用户说明中读取。

推荐本机配置目录：

```text
~/.config/skills/jz-setup-auto-pr/
```

不要把真实 token、本机绝对路径、真实账号、私有部署细节写进 repo。

## Agent 配置

开始接入或测试前，必须确认当前本地 Agent 配置。不要只看 workflow 里的 runner label 或 step 名；真正生效的是 dispatcher 读取到的配置。

读取顺序：

1. `AUTO_PR_AGENT`
2. `<auto-pr-config-dir>/config.yml`、`config.yaml` 或 `config.toml` 的 `agent` 字段
3. 未设置时默认 `codex`

检查当前配置：

```bash
<dispatcher-path> --version
cat <auto-pr-config-dir>/config.yml
command -v codex
command -v claude
```

如果用户要求使用 Claude Code，确认 dispatcher 版本至少是 `0.3.7`，并写入本机未跟踪配置：

```yaml
agent: claude-code
```

然后确认 `claude` CLI 可用：

```bash
claude --version
```

如果用户要求改回 Codex，写入：

```yaml
agent: codex
```

测试时必须检查：

- issue 的第一条 Auto PR 评论里有 `Agent: claude-code` 或 `Agent: codex`。
- 分支前缀匹配 Agent，例如 `claude-code/issue-...` 或 `codex/issue-...`。
- dispatcher log 文件名匹配 Agent，例如 `claude-code.log` 或 `codex.log`。
- PR 已创建，并且 issue comment 里出现对应 Agent 的 final message。

## 接入流程

### 1. 安装或更新 dispatcher

本 skill 自带 dispatcher 模板：

```text
references/jz-auto-pr-dispatch.sh
```

模板内有版本号：

```bash
AUTO_PR_DISPATCH_VERSION="0.3.8"
```

开始接入 repo 前，先运行 installer。它会在 dispatcher 不存在或版本落后时安装/更新：

```bash
<skill-dir>/scripts/install-dispatcher.sh
```

默认安装到：

```text
<home-dir>/.local/bin/jz-auto-pr-dispatch
```

可用环境变量覆盖：

```bash
AUTO_PR_DISPATCH_PATH=<dispatcher-path> <skill-dir>/scripts/install-dispatcher.sh
```

检查版本：

```bash
<dispatcher-path> --version
```

installer 还会创建默认映射文件：

```text
<home-dir>/.config/skills/jz-setup-auto-pr/repos.json
```

不要把 token 写进 skill repo。PR 创建 token 放在本机未跟踪配置中，或通过 `AUTO_PR_GITHUB_TOKEN` 注入。

dispatcher 默认调用 Codex CLI。需要改用 Claude Code 时，在 runner 环境中设置：

```bash
AUTO_PR_AGENT=claude-code
```

也可以写入本机未跟踪配置：

```yaml
agent: claude-code
```

支持值：

- `codex`：执行 `codex exec`。
- `claude-code`：执行 `claude --print`。

dispatcher 默认打开 macOS 系统通知：

- 接收任务时通知：`Auto PR started`。
- 完成 PR 时通知：`Auto PR completed`。
- 失败时通知：`Auto PR failed`。

dispatcher 完成或失败时会优先调用 `jz-notify`：

- 系统通知和飞书由 `jz-notify` 统一发送。
- 默认查找 `$HOME/.codex/skills/jz-notify/scripts/notify.sh`、`$HOME/.agents/skills/jz-notify/scripts/notify.sh`、`$HOME/.claude/skills/jz-notify/scripts/notify.sh`。
- 可用 `AUTO_PR_NOTIFY_SCRIPT` 覆盖通知脚本路径。
- 可用 `AUTO_PR_NOTIFY=0` 关闭完成/失败通知。
- 如果找不到 `jz-notify`，回退为 macOS 系统通知。

如果某台 runner 不适合弹系统通知，可在 runner 环境里设置：

```bash
AUTO_PR_MACOS_NOTIFY=0
```

### 2. 检查 runner

确认已有 self-hosted runner，且 online。

默认先查 org 级 runner。优先使用本机允许的 owner 作为 org：

```bash
gh api /orgs/<allowed-owner>/actions/runners \
  --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

如果没有在线 runner，再退回到 repo remote 的 owner：

```bash
gh api /orgs/<owner>/actions/runners \
  --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

如果 owner 不是 org，或 owner 级没有 runner，再查 repo 级 runner：

```bash
gh api repos/<owner>/<repo>/actions/runners \
  --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

如果三个位置都没有在线 runner，不要在这个 skill 里从头安装 runner，除非用户明确要求。先说明需要注册 runner。

### 3. 确认本机 checkout

本机 checkout 指用户机器上已经 clone 的目标 repo。

检查：

```bash
git -C <local-checkout> remote get-url origin
git -C <local-checkout> status --short --branch
```

要求：

- `origin` 指向 `<owner>/<repo>`。
- 不要求 checkout 在 `main`，因为 dispatcher 会从 `origin/main` 创建 worktree。
- 不要改动用户当前 checkout 的 branch 或未提交文件。

### 4. 确认 repo owner 和映射

先从 remote 解析 `<owner>/<repo>`：

```bash
git -C <local-checkout> remote get-url origin
```

先读取允许的 owner：

```bash
cat <auto-pr-config-dir>/allowed-owner
```

如果未设置，先询问用户默认接入哪个 GitHub owner，并写入本机未跟踪配置。不要把真实 owner 写进 skill repo。

如果 remote owner 与允许的 owner 不一致，停下询问用户：

```text
当前 repo remote 是 <owner>/<repo>，不在 <allowed-owner> 下。是否要先迁移到 <allowed-owner>，再接入 Auto PR？
```

用户确认迁移前，不要：

- 添加 Auto PR workflow。
- 写入 repo 映射。
- 注册或修改 runner 配置。
- 创建测试 issue。

迁移不在本 skill 内直接完成。用户确认后，按项目当前发布/迁移规则处理 GitHub repo 迁移；迁移完成并确认 remote 指向 `<allowed-owner>/<repo>` 后，再继续本 skill。

然后检查 repo 是否已经在映射文件中：

```bash
jq -er --arg repo "<owner>/<repo>" '.[$repo]' <auto-pr-config-dir>/repos.json
```

如果当前 repo 不在映射里，停下询问用户：

```text
当前 repo <owner>/<repo> 不在 Auto PR repo 映射里。是否把它加入映射，指向当前 checkout？
```

用户确认前，不要写入映射文件。用户拒绝时，标记为 `blocked` 或 `skipped`，不要继续添加 workflow；否则 workflow 会触发 dispatcher，但 dispatcher 找不到本机目录。

### 5. 更新 repo 映射

把目标 repo 加到 dispatcher 使用的映射文件。

示例：

```json
{
  "<owner>/<repo>": "<local-checkout>"
}
```

更新后检查 JSON：

```bash
jq . <auto-pr-config-dir>/repos.json >/dev/null
```

如果映射文件已经有该 repo，先确认路径是否仍然正确，不要重复添加。

### 6. 添加 workflow

在目标 repo 添加：

```text
.github/workflows/auto-pr.yml
```

默认模板：

```yaml
name: Auto PR

on:
  issues:
    types:
      - opened
      - reopened
  issue_comment:
    types:
      - created
  workflow_dispatch:
    inputs:
      issue_number:
        description: GitHub issue number to process
        required: true
        type: number

permissions:
  contents: write
  issues: write
  pull-requests: write

concurrency:
  group: auto-pr-${{ github.repository }}
  cancel-in-progress: false

jobs:
  auto-pr:
    if: >-
      (github.event_name == 'issues' &&
        (github.event.issue.author_association == 'OWNER' ||
         github.event.issue.author_association == 'MEMBER' ||
         github.event.issue.author_association == 'COLLABORATOR')) ||
      (github.event_name == 'issue_comment' &&
        !github.event.issue.pull_request &&
        startsWith(github.event.comment.body, '/auto-pr') &&
        (github.event.comment.author_association == 'OWNER' ||
         github.event.comment.author_association == 'MEMBER' ||
         github.event.comment.author_association == 'COLLABORATOR')) ||
      github.event_name == 'workflow_dispatch'
    runs-on:
      - self-hosted
      - auto-pr
      - codex
    timeout-minutes: 180

    steps:
      - name: Dispatch local auto PR
        env:
          EVENT_NAME: ${{ github.event_name }}
          EVENT_ISSUE_NUMBER: ${{ github.event.issue.number }}
          INPUT_ISSUE_NUMBER: ${{ inputs.issue_number }}
          REPOSITORY: ${{ github.repository }}
          ACTOR: ${{ github.actor }}
          GH_TOKEN: ${{ github.token }}
          GITHUB_TOKEN: ${{ github.token }}
        run: |
          set -euo pipefail
          issue_number="$EVENT_ISSUE_NUMBER"
          if [ "$EVENT_NAME" = "workflow_dispatch" ]; then
            issue_number="$INPUT_ISSUE_NUMBER"
          fi

          "$HOME/.local/bin/jz-auto-pr-dispatch" \
            --repo "$REPOSITORY" \
            --issue "$issue_number" \
            --actor "$ACTOR"
```

判断：

- 默认只有 OWNER、MEMBER 或 COLLABORATOR 创建或 reopen 的 issue 才进入 Auto PR。
- 同一 repo 的 Auto PR run 默认按 repo 级队列串行执行，避免多个 issue 同时撞到本机 dispatcher 的 repo lock。
- 如果某个 repo 的 issue 经常是想法、讨论或需求澄清，先和用户确认是否要给该 repo 改成 label/comment 模式。
- 不要让自动化 merge PR。
- 不要让自动化 approve 自己的 PR。

### 7. 提交 workflow

在目标 repo 中提交 workflow。

提交前检查：

```bash
git diff --check
```

如果项目有 YAML lint，可以运行。没有就至少用 `ruby -e`、`python` 或项目已有工具解析 YAML；不引入新依赖。

提交信息示例：

```text
Add Auto PR issue trigger
```

如果项目规则要求先 PR，不要直接 push 到 `main`。

### 8. 测试

测试顺序：

1. 创建一个真实但低风险的 issue。
2. 用选定触发方式启动：
   - 默认：创建 issue 后自动触发。
   - 手动重跑：评论 `/auto-pr`。
3. 查看 Actions run。
4. 查看本机 dispatcher log。
5. 查看 issue comment。
6. 查看是否创建 agent 对应的 auto-pr branch。
7. 查看是否创建 PR。

常用命令：

```bash
gh run list -R <owner>/<repo> --workflow auto-pr.yml --limit 5
```

```bash
gh pr list -R <owner>/<repo> --state open \
  --json number,title,headRefName,url,closingIssuesReferences
```

```bash
git -C <local-checkout> worktree list
```

如果 PR 创建失败但 branch 已 push，先保留成果，手动创建 PR，再修 auth 或 dispatcher。不要重跑导致重复 branch。

## Dispatcher 要求

dispatcher 应至少做到：

- 只接受 allowlist owner 或 allowlist repo。
- 从映射文件读取 repo 到本机 checkout 的关系。
- 校验 checkout 的 `origin` remote 匹配事件 repo。
- 对同一 repo 加 lock，避免并发改同一项目。
- 从 `origin/<base-branch>` 创建独立 worktree。
- 生成清楚的 Agent prompt：
  - 只处理当前 issue。
  - 读取项目说明。
  - 遵守 package manager。
  - 不 push base branch。
  - 不部署生产。
  - 验证后 commit、push、创建 PR。
- 保存 logs 和 Agent final message。
- 公开评论 issue 前，对 Agent final message 做本机绝对路径脱敏。
- 成功或失败都评论回 issue。

如果当前 dispatcher 还没有这些能力，先从本 skill 的 reference 模板安装或更新 dispatcher，再接入新 repo。

## PR 完成后的提醒

默认推荐：

- PR 创建后评论 issue，包含 PR URL。
- 自动把 PR assign 给用户。
- 自动把用户加为 reviewer。
- dispatcher 接收任务时默认发送 macOS notification。
- dispatcher 完成或失败时默认调用 `jz-notify`，至少覆盖系统通知和飞书；找不到 `jz-notify` 时回退到 macOS notification。

可选提醒：

- Telegram、飞书、Slack、Discord webhook：适合日常提醒。
- ntfy、Pushover、Bark：适合手机推送。
- SMS 或电话：只用于高价值任务或失败告警。

不要默认打电话或发短信，除非用户明确要求。

不要默认创建飞书 webhook 或写入飞书凭证；凭证只放在 `jz-notify` 的本机未跟踪配置里。

## 安全规则

- 不提交 token、secret、cookie、private key。
- 不把本机绝对路径写进 repo。
- 不把真实账号、客户名、私有域名写进公开文件。
- 不自动 merge。
- 不自动 approve。
- 不直接部署生产。
- 不删除远端 branch，除非用户明确要求。
- 不清理用户未确认的 worktree。
- 不修改无关 workflow。

## 最终汇报

汇报这些信息：

- 修改了哪个 repo。
- 添加或更新了哪个 workflow。
- repo owner 是否匹配本机允许 owner；如果不是，用户是否确认迁移。
- 映射文件是否已更新。
- runner 是否 online。
- dispatcher 版本和路径。
- 本地 Agent 配置值。
- 触发策略是否为默认处理所有新 issue。
- 测试 issue、Actions run、PR 链接。
- 哪些验证已跑，哪些没有跑。
- 仍需用户配置的权限、token 或通知渠道。
