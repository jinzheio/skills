---
name: jz-set-auto-pr
description: "把 GitHub repo 接入本机 Auto PR runner。适用于用户要求为新项目配置 issue 触发的 Codex Auto PR、self-hosted runner workflow、repo 到本机 checkout 映射、dispatcher 配置和测试 issue。触发词包括 auto PR、自动提 PR、issue auto PR、self-hosted runner、Codex runner、GitHub issue trigger、扩展到新 repo。"
---

# GitHub Issue Triggered Auto PR

把已有 GitHub repo 接入本机 Auto PR runner。

现在的默认流程是：

1. GitHub issue 触发 workflow。
2. GitHub Actions 把 job 派给已注册的 self-hosted runner。
3. runner 执行本机 dispatcher。
4. dispatcher 根据 repo 映射找到本机 checkout。
5. dispatcher 创建独立 worktree 和 `codex/*` branch。
6. Codex CLI 在 worktree 里处理 issue、验证、commit、push、创建 PR。
7. dispatcher 把结果评论回 issue。

这个 skill 不负责 Cloudflare preview。PR preview、生产部署、Worker/Pages 清理交给部署相关 skill 或项目已有 workflow。

## 先确认

开始前确认这些信息：

- GitHub repo：`<owner>/<repo>`。
- base branch：通常是 `main`。
- 本机 checkout：用户机器上已经 clone 的目标 repo。
- dispatcher 路径：默认 `<home-dir>/bin/jz-auto-pr-dispatch`，可用 `AUTO_PR_DISPATCH_PATH` 覆盖。
- repo 映射配置：例如 `<auto-pr-config-dir>/repos.json`。
- self-hosted runner label：至少包含 `self-hosted`，建议另有 `auto-pr` 和 `codex`。
- 触发策略：
  - 保守模式：`codex:auto-pr` label 或 `/auto-pr` comment。
  - 默认处理模式：`issues.opened` 直接触发。
- PR 创建身份：优先使用 dispatcher 注入的本机 token，不要求打开 org 级 “Allow GitHub Actions to create and approve pull requests”。

如果用户只是问机制，先解释，不改文件。如果用户要求配置，直接改目标 repo 和本机配置。

## 配置位置

skill 文档中的路径都用占位符。实际路径从当前机器、已有 dispatcher 或用户说明中读取。

推荐本机配置目录：

```text
~/.config/skills/jz-set-auto-pr/
```

已有机器可能仍使用旧位置。遇到旧位置时可以继续兼容，但新增文档和示例优先写推荐目录。

不要把真实 token、本机绝对路径、真实账号、私有部署细节写进 repo。

## 接入流程

### 1. 安装或更新 dispatcher

本 skill 自带 dispatcher 模板：

```text
references/jz-auto-pr-dispatch.sh
```

模板内有版本号：

```bash
AUTO_PR_DISPATCH_VERSION="0.3.1"
```

开始接入 repo 前，先运行 installer。它会在 dispatcher 不存在或版本落后时安装/更新：

```bash
<skill-dir>/scripts/install-dispatcher.sh
```

默认安装到：

```text
<home-dir>/bin/jz-auto-pr-dispatch
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
<home-dir>/.config/skills/jz-set-auto-pr/repos.json
```

不要把 token 写进 skill repo。PR 创建 token 放在本机未跟踪配置中，或通过 `AUTO_PR_GITHUB_TOKEN` 注入。

### 2. 检查 runner

确认 org 或 repo 已有 self-hosted runner，且 online。

可用命令示例：

```bash
gh api /orgs/<owner>/actions/runners \
  --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

如果是 repo 级 runner：

```bash
gh api repos/<owner>/<repo>/actions/runners \
  --jq '.runners[] | {name,status,busy,labels:[.labels[].name]}'
```

如果没有 runner，不要在这个 skill 里从头安装 runner，除非用户明确要求。先说明需要注册 runner。

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

### 4. 更新 repo 映射

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

### 5. 添加 workflow

在目标 repo 添加：

```text
.github/workflows/auto-pr.yml
```

保守模式模板：

```yaml
name: Auto PR

on:
  issues:
    types:
      - labeled
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
  group: auto-pr-${{ github.repository }}-${{ github.event.issue.number || inputs.issue_number }}
  cancel-in-progress: false

jobs:
  auto-pr:
    if: >-
      (github.event_name == 'issues' &&
        github.event.label.name == 'codex:auto-pr') ||
      (github.event_name == 'issue_comment' &&
        !github.event.issue.pull_request &&
        startsWith(github.event.comment.body, '/auto-pr') &&
        contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)) ||
      github.event_name == 'workflow_dispatch'
    runs-on:
      - self-hosted
      - auto-pr
      - codex
    timeout-minutes: 180

    steps:
      - name: Dispatch local Codex auto PR
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

          "$HOME/bin/jz-auto-pr-dispatch" \
            --repo "$REPOSITORY" \
            --issue "$issue_number" \
            --actor "$ACTOR"
```

默认处理模式只在用户明确要求时使用。把 `on.issues.types` 改成 `opened` 或增加 `opened`，并调整 job `if`：

```yaml
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

jobs:
  auto-pr:
    if: >-
      (github.event_name == 'issues') ||
      (github.event_name == 'issue_comment' &&
        !github.event.issue.pull_request &&
        startsWith(github.event.comment.body, '/auto-pr') &&
        contains(fromJSON('["OWNER","MEMBER","COLLABORATOR"]'), github.event.comment.author_association)) ||
      github.event_name == 'workflow_dispatch'
```

保守判断：

- 如果 repo 的 issue 里经常有想法、讨论、需求澄清，使用保守模式。
- 如果 repo 的 issue 基本都是明确小任务，可以使用默认处理模式。
- 不要让自动化 merge PR。
- 不要让自动化 approve 自己的 PR。

### 6. 提交 workflow

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

### 7. 测试

测试顺序：

1. 创建一个真实但低风险的 issue。
2. 用选定触发方式启动：
   - 保守模式：添加 `codex:auto-pr` label，或评论 `/auto-pr`。
   - 默认处理模式：创建 issue 后自动触发。
3. 查看 Actions run。
4. 查看本机 dispatcher log。
5. 查看 issue comment。
6. 查看是否创建 `codex/*` branch。
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
- 生成清楚的 Codex prompt：
  - 只处理当前 issue。
  - 读取项目说明。
  - 遵守 package manager。
  - 不 push base branch。
  - 不部署生产。
  - 验证后 commit、push、创建 PR。
- 保存 logs 和 Codex final message。
- 成功或失败都评论回 issue。

如果当前 dispatcher 还没有这些能力，先从本 skill 的 reference 模板安装或更新 dispatcher，再接入新 repo。

## PR 完成后的提醒

默认推荐：

- PR 创建后评论 issue，包含 PR URL。
- 自动把 PR assign 给用户。
- 自动把用户加为 reviewer。

可选提醒：

- macOS notification：适合本机前工作。
- Telegram、飞书、Slack、Discord webhook：适合日常提醒。
- ntfy、Pushover、Bark：适合手机推送。
- SMS 或电话：只用于高价值任务或失败告警。

不要默认打电话或发短信，除非用户明确要求。

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
- 映射文件是否已更新。
- runner 是否 online。
- dispatcher 版本和路径。
- 触发策略是 label/comment 还是默认处理所有新 issue。
- 测试 issue、Actions run、PR 链接。
- 哪些验证已跑，哪些没有跑。
- 仍需用户配置的权限、token 或通知渠道。
