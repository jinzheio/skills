---
name: jz-build-personal-context
version: "1.0.0"
description: "当用户想通过访谈、苏格拉底提问或交互式方式创建或更新 about.md、voice.md、anti-style.md，并让 Codex、ChatGPT、Claude、Claude Code 使用这些个人上下文文件时使用。触发语包括 create about me、update aboutme、review personal context、voice profile、anti AI writing style、个人上下文、写作风格文件、全局 AI profile、-g 自动开启。用户在对话中途要求更新 aboutme 文件时，也用本 skill 回顾当前 session 并判断各文件是否需要更新。不是用于写单篇文章或普通润色。"
---

# 个人上下文构建

通过访谈创建三份长期上下文文件，并把它们接入常用 agent。

## 目标文件

默认创建：

- `about.md`
- `voice.md`
- `anti-style.md`

可选创建：

- `chatgpt-custom-instructions.md`
- `claude-project-instructions.md`

## 工作流

### 1. 先问输出位置和接入范围

如果用户没有指定目录，默认使用 `~/Projects/aboutme/`。三份目标文件直接放在这个目录下。

如果用户说 `-g`、`global`、`全局开启` 或 `四项都开启`，接入范围使用：

- Codex
- ChatGPT
- Claude
- Claude Code

否则先问要接入哪些入口。不要在未确认时修改全局配置文件。

### 2. 判断模式

如果目标文件不存在，进入“创建模式”，按后续苏格拉底式访谈创建三份文件。

如果用户在对话中途说“更新 aboutme”“更新个人上下文”“review personal context”“刚才这段也写进 profile”等，进入“Review and Update 模式”：

1. 先读取 `~/Projects/aboutme/about.md`、`voice.md`、`anti-style.md`。
2. 回顾当前 session 中用户已经明确表达的信息，只使用本 session 可见内容，不猜测历史对话。
3. 按文件分类判断：
   - `about.md`：身份、目标、约束、已做决定、业务状态是否变化。
   - `voice.md`：读者、表达方式、文章开头、判断方式、常用表达是否变化。
   - `anti-style.md`：禁用词、禁用结构、禁用语气、UI/产品文案规则是否变化。
4. 输出审计结果：
   - `需要更新`：列出建议新增、修改或删除的条目。
   - `无需更新`：说明当前文件已经覆盖。
   - `信息不足`：问 1 个编号问题确认。
5. 不要把临时情绪、一次性任务、未确认事实写进长期文件。
6. 如果用户明确要求“直接更新”，可在审计后直接编辑；否则先给出建议变更，等待用户确认。
7. 更新后汇报改了哪些文件、每个文件改了什么。

Review and Update 模式不要求每个文件再问 5-10 个问题；只有信息不足时才进入单题追问。

### 3. 苏格拉底式访谈

访谈必须采用单题递进方式：

- 每次只问 1 个问题。
- 每个问题必须带连续编号，例如 `Q1`、`Q2`。
- 每个目标文件至少问 5 个问题，最多问 10 个问题。
- 根据用户上一题回答调整下一题，不要一次性列出固定问题清单。
- 每题先追事实，再追判断，再追取舍，逐步深入用户本意。
- 如果用户回答含糊，下一题优先追问含糊处。
- 如果用户主动给出大量信息，可以把信息计入后续问题，但仍要继续按单题方式确认关键判断。
- 达到 5 题后，如果信息已经足够，可以先总结“已确认答案”和“仍缺信息”，再进入下一份文件。
- 达到 10 题后，必须停止追问该文件，先生成草稿或总结缺口。

访谈记录要保留问题编号，便于最后汇总答案。

按这个顺序访谈：

1. `about.md`
   - 当前身份和业务
   - 正在推进的目标
   - 已经做出的决定
   - 近期约束
   - AI 不应该反复建议的方向
   - 这些信息哪些可以长期使用，哪些只适用于当前阶段

2. `voice.md`
   - 常写内容和读者
   - 常用句式、节奏、结构
   - 观点、判断方式和边界
   - 喜欢的表达样例
   - 不会说的话
   - 不同场景是否需要不同语气

3. `anti-style.md`
   - 禁用词
   - 禁用结构
   - 禁用语气
   - 格式规则
   - 改写前后样例
   - 哪些错误一出现就应该重写

每个文件的访谈结束后，按问题编号汇总答案，再生成对应草稿。不要在 5 题之前生成文件，除非用户明确要求提前结束。

### 4. 生成文件

文件用中文写，除非用户要求英文。保留必要英文技术标识。

写法要求：

- 用事实和规则，不写产品愿景句。
- 不写空泛形容词。
- 不替用户编造经历、账号、客户、收入或项目。
- 不写真实隐私信息，除非用户明确要求本地私用。
- 对外可分享版本必须把账号、客户、路径、联系人和密钥替换成占位符。

### 5. 用户确认

生成三份文件后，先让用户检查：

- 哪些内容不准
- 哪些内容太泛
- 哪些规则会让 AI 过度收缩

用户确认后再执行安装脚本。

### 6. 安装到各入口

使用 `scripts/install-profile.mjs`。

常用命令：

```bash
node build-personal-context/scripts/install-profile.mjs -g
```

本地 npx 入口：

```bash
npx --yes ./build-personal-context -g
```

只接入部分入口：

```bash
node build-personal-context/scripts/install-profile.mjs --targets codex,claude-code
```

dry run：

```bash
node build-personal-context/scripts/install-profile.mjs -g --dry-run
```

脚本默认使用 `~/Projects/aboutme/` 作为源目录和共享 profile 目录，然后：

- 为 Codex 写入全局 `AGENTS.md` 管理块，按任务类型引用三份文件。
- 为 Claude Code 写入全局 `CLAUDE.md` 管理块，按任务类型引用三份文件。
- 为 ChatGPT 生成 custom instructions 文件。
- 为 Claude Chat/Project/Cowork 生成 project/global instructions 文件。

ChatGPT 和 Claude Chat 通常不能直接读取本机文件。对这两个入口，脚本生成可粘贴或上传到 Project knowledge 的说明文件；不要声称它们已经自动读取了本机路径。

## 完成条件

- 三份目标文件存在。
- 内容来自用户回答，未补写无法确认的事实。
- 默认位置是 `~/Projects/aboutme/`，除非用户指定其它目录。
- `-g` 时四类入口都有对应接入物。
- 全局文件只更新脚本标记的管理块，不覆盖用户已有内容。
- 最后报告安装位置、接入范围和需要用户手动粘贴/上传的文件。
