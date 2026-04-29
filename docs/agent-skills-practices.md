# Agent Skills 社区最新实践总结

> 整理时间：2026-04-29  
> 适用格式：SKILL.md / Claude Agent SDK / 开放 Agent Skills 规范

---

## 一、什么是 Agent Skills

Agent Skills 是一种将领域知识打包为可复用能力的标准格式，让通用 AI agent 能够被专门化为胜任特定任务的专家。Anthropic 工程博客将其比作"新员工入职手册"：不必为每个用例从头构建专用 agent，而是通过可组合的 skill 让任何 agent 获得所需的程序性知识。

一个 skill 是一个目录，核心是 `SKILL.md` 文件，可选包含 `scripts/`、`assets/`、`references/` 等子目录。格式已被 Claude、OpenAI Codex、Gemini CLI、Cursor 等主流 AI 编程工具采纳，具备良好的跨平台兼容性。

---

## 二、核心设计原则：渐进式披露（Progressive Disclosure）

渐进式披露是 2025–2026 年社区公认的 Agent Skills 核心设计模式，目标是让 agent 只在需要时加载所需上下文，避免无谓的 token 消耗。

其工作分三个层级展开：

**第一层：元数据（~100 tokens/skill）**  
SKILL.md 的 YAML frontmatter 字段 `name` 和 `description` 在 agent 启动时预注入系统提示词。这是 agent 判断"是否触发该 skill"的唯一依据，因此必须精准且具有代表性。

**第二层：完整指令（建议 < 5000 tokens）**  
当 agent 判断某个 skill 与当前任务匹配时，才加载完整的 SKILL.md 正文。这一层应包含主要工作流、关键规则和交付物定义，但不必穷举所有边界情况。

**第三层：引用资源（按需加载，无上限）**  
agent 在执行过程中按需读取 `references/`、`assets/` 等补充文件。由于这些文件只在需要时进入上下文，单个 skill 的总信息量实际可以无限扩展。

**实践意义**：SKILL.md 正文越短、越聚焦，agent 的触发决策越准确，context window 的利用率越高。冗长的 SKILL.md 往往是把本该放入 `references/` 的内容写进了主文件。

---

## 三、SKILL.md 文件规范

### 3.1 必需结构

```
skill-name/
├── SKILL.md              # 必需，包含 frontmatter + 正文
├── agents/               # 可选，平台适配配置
│   └── openai.yaml
├── scripts/              # 可选，可执行脚本
├── assets/               # 可选，模板、示例文件
└── references/           # 可选，详细参考文档
```

### 3.2 Frontmatter 字段

```yaml
---
name: skill-name                  # 必需，机器可读的唯一标识
description: "..."                # 必需，agent 触发决策的依据
# 可选扩展字段（平台支持情况不同）：
tools: [bash, read_file]          # 声明所需工具
permissions: [filesystem]         # 声明所需权限
version: "1.0.0"                  # 版本追踪
---
```

### 3.3 Description 写法要点

Description 是 skill 最重要的单行文字，直接影响 agent 的触发准确率。**一个容易被忽视的关键点**：正文里的 `## Use This When` 或 `## Best Fit` 等触发说明对触发决策毫无帮助——agent 只有在已决定触发该 skill 之后才会读到正文，触发判断那一刻只能看到 frontmatter 里的 `description`。把触发条件写在正文等于写给"已经触发后"的 agent 看，对"是否触发"完全无效。

因此，所有触发相关的内容都应该写进 frontmatter 的 `description` 字段。社区总结的三段式结构：

- **用户意图**：这个 skill 解决什么问题
- **典型触发词**：用户可能说的具体短语，如 `"Use when user says 'publish this site', 'push and go live', '帮我 commit'"`
- **不触发的边界**：避免误触发的关键边界，如 `"Not for backend-only repos without public pages"`、`"Use after upstart-site, not before"`

正文里原有的 `## Use This When` 节可以删除，或保留为对已触发 agent 的补充说明，但不能依赖它来帮助触发。

---

## 四、2025–2026 社区最佳实践

### 4.1 从实际任务缺口出发构建

不要凭空预设 skill 的内容。推荐做法：先在真实任务上运行 agent，观察它在哪里失败或需要额外上下文，然后针对性地构建 skill。这样产生的 skill 覆盖的是真实缺口，而非想象中的缺口。

### 4.2 用代码替代 LLM 处理确定性操作

当某个操作需要确定性结果（排序、文件解析、格式验证）或效率要求高时，将其实现为可执行脚本而非 LLM 指令。agent 可以直接运行脚本而不必把文件内容加载进上下文，这同时提升了可靠性和 token 效率。

示例：PDF 技能将"提取表单字段"实现为 Python 脚本，agent 执行脚本拿到结果，无需把整个 PDF 加载到 context window。

### 4.3 拆分过大的 SKILL.md

开放 Agent Skills 规范的建议上限是 500 行，Anthropic 的建议是 5000 tokens，两个标准大致对应。超过这一范围时，通常是需要拆分的信号。社区推荐的拆分策略：

- **互斥路径**：把互相排斥的场景（如"已有 IndexNow"vs"新安装 IndexNow"）拆到独立的 reference 文件
- **可选模块**：把非必经流程（如邮件转发、Clarity 配置）移入 `references/`
- **模板与示例**：把代码模板、配置示例移入 `assets/`，SKILL.md 只保留"如何使用"的说明

### 4.4 与 Claude 迭代，而非独自猜测

Anthropic 推荐的 skill 开发方式：在与 Claude 合作完成真实任务的过程中，请 Claude 将成功的方法和常见错误记录进 skill。如果 Claude 用 skill 出错，请它自我反思并建议改进点。这比独自预测 agent 的需求更有效。

### 4.5 skill 间编排与依赖关系

2026 年的主流模式是将复杂工作流拆分为多个单一职责的 skill，通过显式引用编排：

- 每个 skill 只做一件事（single responsibility）
- 在 SKILL.md 中明确说明"推荐前置 skill"和"推荐后续 skill"
- 避免在一个 skill 里重复实现另一个 skill 的逻辑，改为显式调用

### 4.6 错误恢复与幂等性

生产级 skill 应考虑：

- **幂等操作**：skill 的操作应可安全重试，不产生重复副作用
- **显式检查点**：在产生外部副作用（推送代码、DNS 变更、发布部署）前，必须等待用户确认
- **失败分级**：区分"可自动修复"（如 lockfile 过期）和"必须上报"（如认证失败）的错误
- **完成条件明确**：用验证清单（checklist）定义"任务真正完成"的条件，避免以"平台显示成功"代替实际验证

### 4.7 高风险流程的"计划-验证-执行"结构

对于会产生不可逆外部副作用（DNS 变更、代码推送、域名绑定、环境变量写入）的 skill，仅靠 "Do not" 规则列表来约束 agent 行为是不够稳定的。更有效的模式是在 skill 中要求 agent 先输出一份结构化执行计划，再对照真实状态验证，最后才执行。

**三段式结构示例**（适用于 `new-domain-launch`、`upstart-site` 等）：

1. **Plan**：agent 在动手前先输出：涉及的系统（registrar / DNS provider / hosting）、计划创建的 records、验证命令清单、回滚路径
2. **Validate**：对照平台 API / CLI 的实际返回值确认前提成立（repo 存在？zone 已激活？env 已设置？）
3. **Execute**：逐步执行，每步完成后检查输出再进行下一步

这种结构比"很多 Do not"更 agent-friendly，因为 agent 遵循显式结构比遵循禁令更稳定，也更容易在出错时定位是哪一步失败了。

### 4.8 用 Eval 替代感觉调优

最新实践强调：description 的质量不应凭感觉反复修改，而应通过 eval 来测量和改进。建议在每个 skill 目录下维护 `evals/` 文件夹，每个 skill 至少包含 5–8 条真实用户 prompt，分两类：

- **应触发（positive cases）**：覆盖典型措辞和变体
- **不应触发（negative / near-miss cases）**：这类更重要，测试容易误触发的边界 prompt

近似误触发示例（`jzskills` 的典型风险）：

| Prompt | 预期行为 |
|---|---|
| "帮我 push 这个后端 API 库" | 触发 `push-code` 但**不**运行 IndexNow |
| "域名解析好了，帮我接 GSC" | 触发 `index-onboarding`，**不**触发 `new-domain-launch` |
| "部署到 Vercel 临时域名就行" | 触发 `upstart-site`，**不**继续进入 domain/index onboarding |
| "帮我 commit 一下这几个文件" | 触发 `commit-code`，**不**触发 `push-code` |

在调整 description 后，用这些 eval prompt 对比"修改前 / 修改后"的触发结果，才能知道改动是否真的有效。

### 4.9 安全性

Anthropic 官方提醒：skill 能让 agent 执行代码和访问文件系统，恶意 skill 可能导致数据泄露或非预期操作。推荐实践：

- 只安装来源可信的 skill
- 对来源不明的 skill，在安装前审计所有文件内容，特别关注脚本依赖和对外网络请求
- skill 不应在未获用户确认的情况下连接未知外部服务

---
## 五、参考资料

- [Equipping agents for the real world with Agent Skills — Anthropic Engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Agent Skills — Claude API Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Agent Skills in the SDK — Claude API Docs](https://platform.claude.com/docs/en/agent-sdk/skills)
- [Extend Claude with skills — Claude Code Docs](https://code.claude.com/docs/en/skills)
- [Claude Agent Skills: A First Principles Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/)
- [Agent Skills: Progressive Disclosure as a System Design Pattern](https://www.newsletter.swirlai.com/p/agent-skills-progressive-disclosure)
- [awesome-agent-skills — VoltAgent/GitHub](https://github.com/VoltAgent/awesome-agent-skills)
- [Agents At Work: The 2026 Playbook for Building Reliable Agentic Workflows](https://promptengineering.org/agents-at-work-the-2026-playbook-for-building-reliable-agentic-workflows/)
- [A Practical Guide for Designing, Developing, and Deploying Production-Grade Agentic AI Workflows (arXiv:2512.08769)](https://arxiv.org/abs/2512.08769)
- [Agent Skills Specification — agentskills.io](https://agentskills.io/specification)
- [Optimizing Skill Descriptions — agentskills.io](https://agentskills.io/skill-creation/optimizing-descriptions)
- [Evaluating Skills — agentskills.io](https://agentskills.io/skill-creation/evaluating-skills)
- [Agent Skills — OpenAI Codex Docs](https://developers.openai.com/codex/skills)
