---
name: jz-get-readest-highlights
description: 查询 Readest 书籍列表，或按书名、列表序号读取 Readest 高亮原文 text 和用户批注 note，生成「书名 阅读笔记.md」。用于用户想查看 Readest 书库、导出某本书的原文摘录和自己的批注时。
---

# Readest 阅读笔记

当任务是查询 Readest 书库，或导出某本书的高亮原文和用户批注时使用这个 skill。

## 默认规则

- 主脚本是 `scripts/readest_review.py`。
- 本机配置目录统一使用 `~/.config/skills/jz-get-readest-highlights/`。
- 优先读取 `~/.config/skills/jz-get-readest-highlights/.env`。
- 如果全局 `.env` 不存在，再回退到 skill 目录本地 `.env`。
- 默认输出目录是当前工作目录。
- 默认文件名是 `<书名> 阅读笔记.md`。
- 只导出 Readest 中已有的 `book_notes.text` 和 `book_notes.note`。
- 不做总结、改写、观点提炼或行动建议。
- 不要把 Readest 登录邮箱、密码、anon key 或 access token 写进仓库、命令示例或最终回复。

## 配置

配置文件：

```text
~/.config/skills/jz-get-readest-highlights/.env
```

支持变量：

- `READEST_BASE_URL`：Readest 站点地址，例如 `https://<readest-host>`。
- `READEST_PRIMARY_DOMAIN`：如果没有 `READEST_BASE_URL`，可用域名形式。
- `READEST_ANON_KEY`：Readest Supabase anon key。
- `SUPABASE_ANON_KEY` 或 `ANON_KEY`：兼容部署环境里的 anon key 变量名。
- `READEST_OWNER_EMAIL`：Readest 登录邮箱。
- `READEST_OWNER_PASSWORD`：Readest 登录密码。

也可以用 `JZ_READEST_REVIEW_ENV` 指向另一个 `.env` 文件。

## 查询书籍列表

```bash
uv run python <skill-dir>/scripts/readest_review.py list
```

输出字段：

- 序号
- 书名
- 作者
- 格式
- 阅读状态
- 进度
- 更新时间
- 笔记数

用户说“第 N 本”时，使用这份列表里的序号。

## 生成阅读笔记文档

按序号：

```bash
uv run python <skill-dir>/scripts/readest_review.py notes \
  --index 3 \
  --output-dir .
```

按书名：

```bash
uv run python <skill-dir>/scripts/readest_review.py notes \
  --book "<book-title>" \
  --output-dir .
```

`review` 是旧命令别名，保留兼容；新任务默认使用 `notes`。

脚本会生成：

```text
<书名> 阅读笔记.md
```

文档包含：

- 书籍基本信息
- 高亮和 note 数量
- 用户自己的批注
- 支撑批注的高亮原文
- 没有批注的独立高亮

## 输出要求

- 保留原文和批注的原始表达。
- 如果同一句原文同时存在“独立高亮”和“带批注记录”，不要再单独列出那条独立高亮，只保留带批注记录。
- 有批注时，先输出 `book_notes.note`，下一行接引用格式的 `book_notes.text`。
- 引用末尾用中文括号标注页码和日期，格式为 `（P<页码>/<YYYY-MM-DD>）`；缺失项直接省略。
- 不再为每条记录输出“原文”“批注”小标题，不输出颜色。
- 如果只有高亮没有批注，只输出编号和引用。
- 如果没有高亮或批注，说明“暂无高亮或批注”。

示例：

```markdown
6. 实际上，值得敬佩。我佩服这样的人，但却担心别人笑话自己？这不是矛盾吗？做一个让自己敬佩的人。
> 她一个六十多岁的老人都豁得出去，你还怕什么？（P15/2026-06-28）
```

## 验证

运行后检查：

```bash
test -s "./<书名> 阅读笔记.md"
sed -n '1,80p' "./<书名> 阅读笔记.md"
```

汇报时说明：

1. 使用的是书名还是序号。
2. 匹配到的书名。
3. 读取到多少条高亮、多少条 note。
4. 输出文件路径。
5. 如果没有高亮/批注或匹配到多本书，要说明处理方式。
