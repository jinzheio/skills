---
name: jz-commit-code
version: "1.3.0"
description: "当用户要求 review 并提交本地工作区变更时使用，包括 commit this、帮我 commit、确认提交、split these changes into commits。必须优先分派 subagent 在独立 context window 中执行 review 与提交流程。先 review diff 并报告风险，等待用户明确确认，再按功能创建干净的 scoped commits。除非用户同时要求 push，否则不要推送。当带有 force 参数时（如 commit-code force），跳过确认，自动 review 后直接按功能拆分提交。"
---

# 代码 Review 与提交

对工作区变更做轻量 code review，等待用户确认后，按功能拆分并提交。

## Subagent 启动协议

触发本 skill 后，父 agent 应优先分派一个 subagent 独立执行本 skill，以获得独立的 context window。

父 agent 只负责：

- 创建或复用同一个 subagent
- 向 subagent 传递仓库绝对路径、用户原始请求、本 skill 文件路径和当前确认状态
- 等待 subagent 返回 review 报告、commit 计划、执行结果或 blocker
- 将 subagent 的确认问题转述给用户
- 用户确认后，把确认消息发送给同一个 subagent 继续执行
- 根据 subagent 结果向用户做最终汇报

subagent 的初始任务必须包含：

```text
你在 /absolute/path/to/repo 中执行 commit-code skill。
先阅读仓库内 AGENTS.md 和 commit-code/SKILL.md。
保持脏工作区现状，不要还原用户变更。
[CONFIRMATION_MODE]。
除非用户同时要求 push，否则不要 push。
完成后报告 commit hash、分组和剩余未提交变更。
```

父 agent 负责将上述 `[CONFIRMATION_MODE]` 替换为：
- force 模式（用户请求包含 `force`）：`"跳过所有确认。先 review 工作区 diff 并输出报告，然后直接按功能拆分提交。不要询问用户确认。"`
- 正常模式：`"先 review 工作区 diff 并返回报告，等待用户明确确认后再提交。"`

如果当前环境不支持分派 subagent，才在父 agent 当前 context 中直接执行本流程，并在汇报中说明已降级为本地执行。

## 步骤

### 0. Force 模式

当用户请求包含 `force` 时（如 `commit-code force`、`commit this force`），启用 force 模式：

- 跳过步骤 2 中的用户确认环节。仍然执行步骤 1（review 工作区 diff 并输出报告），但 review 完成后直接进入步骤 3（规划 commit 分组）和步骤 4（逐组提交），不等待用户回复。
- 其余流程与正常模式一致。

### 1. 分析工作区变更

运行 `git status` 查看 tracked 和 untracked 文件。

对每个变更文件：

- tracked 文件运行 `git diff HEAD -- <file>`
- untracked 文件读取完整内容
- 先看完整 diff，再判断风险

保留脏工作区现状。不要 stage、修改、还原或提交与用户请求无关的文件。若存在无关变更，单独列出并保持不动。

**Review 清单：**

1. **逻辑完整性**：新行为是否贯通 API、数据和 UI 边界？
2. **死代码**：是否有未使用变量、import、props、函数、文件或过期分支？
3. **错误处理**：异步失败是否处理？loading / cleanup 状态是否释放？
4. **类型安全**：TypeScript 类型是否匹配真实数据结构？
5. **安全性**：用户输入是否校验？是否有注入、密钥暴露或信任边界问题？
6. **副作用**：轮询、timer、subscription、文件写入或网络请求是否受控并清理？
7. **破坏性变更**：是否影响既有 API、schema、部署流程或运行中的 agent？

按 high / medium / low 分组报告问题。

### 2. 向用户汇报

使用 `assets/review-report.template.md` 的结构报告 review 结果。

如果没有发现问题，明确说明。

然后询问用户：

**“是否确认提交这些变更？如果需要先修复，请告诉我；否则回复 confirm commit。”**

必须等用户明确回复后，才能进入下一步。

### 3. 规划 commit 分组

用户确认后，按功能或模块分组：

- 同一功能的 frontend / backend 文件放在同一个 commit
- 独立 runner、shell、install script 单独 commit
- 纯 UI 或样式变更单独 commit
- 纯文档变更单独 commit
- schema 变更单独 commit，因为可能触发迁移
- untracked 文件放入归属功能的 commit

列出计划，例如：

```text
Commit 1: feat(api): ...
  - src/app/api/...
  - src/app/[locale]/...

Commit 2: feat(runner): ...
  - src/lib/runner/...

Commit 3: docs: ...
  - docs/...
```

### 4. 逐组提交

每组执行：

1. 用精确路径 `git add <file1> <file2> ...`。不要用 `git add .`。
2. 执行：

```bash
git commit -m "<type>(<scope>): <summary>

<bullet points>"
```

使用 Conventional Commits：

- type：`feat` / `fix` / `refactor` / `docs` / `chore` / `style`
- scope：模块名，如 `profile`、`runner`、`api`、`admin`
- summary：英文，50 字符以内，动词开头

### 5. 最终汇报

提交完成后：

- 运行 `git status --short`
- 运行 `git log --oneline -<N>` 展示新 commit
- 向用户报告 commit hash、分组和剩余未提交变更
