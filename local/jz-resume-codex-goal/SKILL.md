---
name: jz-resume-codex-goal
description: 跨项目查找正在运行或刚因 usage/session limit 停下的 Codex App /goal 线程，并在重置后创建一次性 heartbeat 继续执行。适用于用户要求稍后继续 Codex goal、在用量重置后自动 resume、把唤醒绑定到正确 thread、避免长任务手动重启。支持按项目、cwd、标题或 thread id 缩小范围，也支持从可见 limit 文本或本地日志中尽量解析 reset 时间。
---

# Resume Codex Goal

把恢复提醒绑定到真正执行 `/goal` 的线程。除非当前对话就是目标线程，不要把 heartbeat 设在当前对话。

## 流程

1. 找目标线程。
   - 如果线程工具还没加载，先用 `tool_search` 搜 `list_threads`、`read_thread`、`automation_update`。
   - 默认不要限制在当前项目；先用 `list_threads` 列最近线程，必要时增加 `limit`。
   - 用户明确给出项目名、cwd、标题片段或 thread id 时，再用这些条件缩小范围。
   - 用户明确说“当前项目”时，才用当前项目名或 cwd 调 `list_threads`。
   - 优先选择 `status: active`，或最近 turn 仍在进行、首条用户消息以 `/goal` 开头的线程。
   - 如果有多个候选，用 `read_thread` 读最可能的几个，选择标题、cwd、preview 或首条用户消息和用户任务一致的线程。
   - 如果全局只有一个 active/inProgress `/goal` 线程，可以直接选择，并在结果里说明标题和 cwd。
   - 如果仍然无法区分，问用户目标线程标题或能区分它的一段文字。

2. 确定 reset 时间。
   - 用户已经给出时间时，直接使用该时间。
   - 用户没有给时间时，检查目标线程最近消息，找 `try again at ...` 或 `try again in ...`。
   - 需要时，运行 `scripts/infer_reset_time.py` 解析复制出来的 limit 文本；也可以加 `--scan-codex` 在本地 Codex 文件里做一次尽力搜索。
   - 不要仅仅因为 Codex 是 5h 窗口，就用“当前时间 + 5 小时”推断 reset。滚动窗口不足以推出准确重置时间。
   - 在平台提示的 reset 时间后加小缓冲，通常 2 分钟。

3. 清理错误或重复的恢复提醒。
   - 检查 `$CODEX_HOME/automations/*/automation.toml` 或 `~/.codex/automations/*/automation.toml`。
   - 如果已有同类恢复提醒，优先更新，不要重复创建。
   - 如果之前误绑到当前对话或其他线程，先删除或暂停，再创建正确提醒。

4. 创建一次性 heartbeat。
   - 使用 `automation_update`。
   - 设置 `kind: heartbeat`、`destination: thread`，并把 `targetThreadId` 设为目标 `/goal` 线程 id。
   - 用 RRULE 在缓冲后的 reset 时间触发一次。
   - prompt 保持短，并明确要求继续而不是重做：

```text
/goal resume

继续当前 goal。先检查上次进度、未完成项和当前状态；不要从头开始。若当前任务已完成则直接总结并结束；若还没完成，就继续实现和验证，直到完成、明确 blocked，或再次碰到 usage/session limit。如果再次碰到 limit，记录下一次 reset 时间和当前进度。
```

5. 汇报结果。
   - 说明目标线程标题或 id。
   - 说明目标线程所在 cwd，特别是跨项目选择时。
   - 说明准确唤醒时间和时区。
   - 说明是否删除或更新了旧提醒。
   - 如果无法确定 reset 时间，不要创建猜测提醒；让用户提供 Codex 显示的 reset 时间。

## 时间处理

除非用户指定时区，否则使用本机时区。用户只说 `5:59` 时，按本机时区的下一次 5:59 处理，并在创建前说明这个假设。如果当前时间已经过了 5:59，则使用下一天。

RRULE 优先使用：

```text
DTSTART;TZID=<IANA_TIMEZONE>:YYYYMMDDTHHMMSS
RRULE:FREQ=DAILY;COUNT=1
```

## 脚本

用 `scripts/infer_reset_time.py` 从文本或最近的本地 Codex 文件里解析 reset 时间：

```bash
python3 <skill-dir>/scripts/infer_reset_time.py --text "You've hit your usage limit. Try again at 5:59 AM." --grace-minutes 2
python3 <skill-dir>/scripts/infer_reset_time.py --scan-codex --since-hours 12 --grace-minutes 2
```

脚本输出 JSON。`confidence: "low"` 只能作为线索，不能当成确定时间。
