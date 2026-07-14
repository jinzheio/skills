---
name: jz-review-bug
description: 记录 bug、工程错误、事故复盘、调试教训和可复用经验。适用于用户要求“review 这个 bug”“记录到 gbrain”“写复盘文档”“避免再次出错”“把本次错误来源写入知识库”“生成 HKB Wiki 复盘”等场景；输出一条 gbrain learning，并在配置的 HKB 知识库目录下写 Wiki/Notes 复盘文档。
---

# Bug Review

把一次真实调试过程整理成两份产物：

- gbrain learning：短、可检索、偏“以后怎么避免再犯”。
- HKB Wiki note：完整复盘，说明问题、原因、原理、修复、验证和后续动作。

## 配置

读取本机配置：

```text
~/.config/skills/jz-review-bug/config.yml
```

可用 `JZ_BUG_REVIEW_CONFIG` 指向其它配置文件。配置示例见 `config.example.yml`。

兼容旧配置：如果新配置不存在，脚本会尝试读取旧的 `jz-record-postmortem` 配置目录；新任务优先使用 `jz-review-bug`。

必填：

```yaml
hkb_root: "<hkb-root>"
```

可选：

```yaml
wiki_notes_dir: "Wiki/Notes"
gbrain_slug_prefix: "learnings"
gbrain_type: "learning"
```

不要把真实本机路径写进 skill 仓库。真实路径只放在本机未跟踪配置里。

## 流程

1. 还原事实。
   - 读相关代码、diff、日志、命令输出。
   - 区分症状、直接原因、根因、修复和验证。
   - 不要把猜测写成事实；不确定的内容放到“待验证”。

2. 写 HKB 复盘正文。
   - 默认使用中文。
   - 使用 `discussion-note` 结构。
   - 建议章节：
     - `## 问题`
     - `## 结论`
     - `## 原理`
     - `## 修复`
     - `## 不能怎么修`
     - `## 验证`
     - `## 以后遇到同类问题先查什么`
     - `## 后续动作`
   - 保存讨论产物，不保存完整聊天流水。

3. 写 gbrain learning 正文。
   - 比 HKB 短。
   - 聚焦未来检索：症状、判断路径、排查顺序、项目里的修复方式。
   - 标题和正文要包含以后会搜索的关键词，例如错误文本、框架名、工具名。

4. 写后复审。
   - 重新对照用户的 `voice.md` 和 `anti-style.md`，如果当前任务环境有这些文件。
   - 删除空泛判断、夸张语气、课程销售页口吻、无证据结论。
   - 优先写具体观察、命令、文件、验证结果。

5. 保存产物。
   - 先把两份正文放到临时文件。
   - 运行脚本：

```bash
python3 <skill-dir>/scripts/save-postmortem.py \
  --title "Next.js 后端 spawn Claude ENOENT 复盘" \
  --slug "next-spawn-cli-path" \
  --hkb-body-file "<tmp-dir>/hkb-note.md" \
  --gbrain-body-file "<tmp-dir>/gbrain-learning.md" \
  --source "../project/app/api/example/route.ts" \
  --related "[[AI Coding Agents]]" \
  --tag nextjs \
  --tag node-spawn
```

脚本会：

- 从配置读取 HKB 根目录。
- 在 `<hkb_root>/<wiki_notes_dir>/<date>-<slug>.md` 写 HKB note。
- 调用 `gbrain capture --slug <prefix>/<slug> --type <gbrain_type> --stdin` 写 gbrain。

## 命名

- `slug` 用英文小写、数字和连字符，例如 `next-spawn-cli-path`。
- HKB 文件名自动加日期前缀：`YYYY-MM-DD-<slug>.md`。
- gbrain 默认 slug：`learnings/<slug>`。

## 汇报

最终回复说明：

- gbrain slug。
- HKB Wiki 文件路径。
- 是否完成写后复审。
- 如果没写入 gbrain 或 HKB，说明失败原因和保留的临时文件位置。
