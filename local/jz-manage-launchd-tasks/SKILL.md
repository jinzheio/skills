---
name: jz-manage-launchd-tasks
description: 创建、整理、排查 macOS launchd 定时任务和后台任务。触发：需要创建定时任务、登录启动项、后台常驻服务、LaunchAgent、LaunchDaemon、launchctl、修复登录项显示成 bash、给后台任务创建 wrapper、清理失效 launchd 任务。
---

# macOS launchd 任务

## 职责

帮助用户在 macOS 上创建、整理和排查 `launchd` 任务。默认处理用户级 `LaunchAgent`；只有任务必须以 root 或系统级权限运行时，才考虑 `LaunchDaemon`。

优先目标：

- 任务名能从系统设置里看懂。
- 每个任务能单独开关、单独看日志、单独排错。
- 不改变原脚本逻辑、运行频率、工作目录和日志路径。
- 不把真实密钥、账号、本机绝对路径写进仓库文档。

## 判断任务类型

| 需求 | 推荐 |
|------|------|
| 登录后运行、访问用户目录、跑项目脚本 | `~/Library/LaunchAgents/*.plist` |
| 定时采集、每天巡检、每小时同步 | 用户级 `LaunchAgent` + `StartCalendarInterval` 或 `StartInterval` |
| 本地 Web 面板、监控进程，需要挂了重启 | 用户级 `LaunchAgent` + `KeepAlive` |
| 需要 root、开机未登录也要运行、管理系统网络 helper | `/Library/LaunchDaemons/*.plist` |

不确定时，先用用户级 `LaunchAgent`。

## 命名规则

### Label

`Label` 使用稳定、可搜索的反域名形式：

```text
io.<owner>.<project>.<task>
```

示例：

```text
io.example.site-metrics
io.example.cost-monitor
com.example.project.health-check
```

### 系统设置显示名

macOS「登录项与扩展」常按 `ProgramArguments[0]` 的可执行文件名显示。不要让它指向 `/bin/bash`，否则用户会看到一串 `bash`。

推荐创建 wrapper：

```text
$HOME/Library/Scripts/LaunchAgents/<readable-task-name>
```

wrapper 内容：

```bash
#!/usr/bin/env bash
exec <project-script-path> "$@"
```

然后让 plist 指向 wrapper：

```xml
<key>ProgramArguments</key>
<array>
  <string>$HOME/Library/Scripts/LaunchAgents/<readable-task-name></string>
</array>
```

这样系统设置里显示 `<readable-task-name>`，同时原脚本仍然保留在项目仓库里。

## wrapper 还是总入口

默认选 wrapper，不要把多个任务合成一个总入口。

wrapper 更适合这些情况：

- 任务频率不同。
- 有的任务是定时，有的任务是常驻。
- 需要单独查看日志和退出码。
- 某个任务失败不应影响其它任务。
- 用户希望后台列表可读，而不是减少到一个项目名。

只有在这些条件同时满足时，才考虑总入口：

- 所有子任务同频率、同生命周期。
- 可以接受同一个日志文件。
- 失败处理策略完全一致。
- 用户明确想用一个调度器管理这些任务。

如果只是为了让后台列表好看，用 wrapper。

## 创建流程

1. 确认原脚本可直接执行。

```bash
head -n 1 <project-script>
ls -l <project-script>
```

脚本应有 shebang，例如：

```bash
#!/usr/bin/env bash
```

如果没有执行权限：

```bash
chmod +x <project-script>
```

2. 创建 wrapper。

```bash
mkdir -p "$HOME/Library/Scripts/LaunchAgents"
```

```bash
cat > "$HOME/Library/Scripts/LaunchAgents/<readable-task-name>" <<'EOF'
#!/usr/bin/env bash
exec <project-script-path> "$@"
EOF
chmod +x "$HOME/Library/Scripts/LaunchAgents/<readable-task-name>"
```

如果正在修改仓库文件，用 `apply_patch` 创建文件；如果是在用户本机配置目录创建一次性 wrapper，可以用 shell 写入。

3. 创建或更新 plist。

最小用户级定时任务：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>io.example.project.task</string>

  <key>ProgramArguments</key>
  <array>
    <string><home>/Library/Scripts/LaunchAgents/example-task</string>
  </array>

  <key>WorkingDirectory</key>
  <string><project-dir></string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>

  <key>StandardOutPath</key>
  <string><log-dir>/task.log</string>
  <key>StandardErrorPath</key>
  <string><log-dir>/task.log</string>
</dict>
</plist>
```

本机实际 plist 可以使用真实路径；仓库文档和 skill 内容里使用占位符。

4. 验证 plist。

```bash
plutil -lint "$HOME/Library/LaunchAgents/<label>.plist"
```

5. 重新加载。

```bash
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/<label>.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/<label>.plist"
```

6. 检查 launchd 状态。

```bash
launchctl list | rg '<label>|<readable-task-name>'
```

7. 检查系统设置显示名。

```bash
sfltool dumpbtm 2>/dev/null | rg -i -C 3 '<readable-task-name>|Name: bash'
```

如果仍显示 `bash`，检查 `ProgramArguments[0]` 是否还指向 `/bin/bash`。

## 整理已有 bash 登录项

遇到系统设置里一串 `bash` 时：

1. 找出来源。

```bash
rg -n '/bin/bash|<suspected-script-name>' \
  "$HOME/Library/LaunchAgents" \
  /Library/LaunchAgents \
  /Library/LaunchDaemons 2>/dev/null
```

2. 展开 plist。

```bash
plutil -p "$HOME/Library/LaunchAgents/<label>.plist"
```

3. 为每个任务创建可读 wrapper。

4. 把 plist 的 `ProgramArguments` 改成只指向 wrapper。

```bash
/usr/libexec/PlistBuddy \
  -c "Delete :ProgramArguments" \
  -c "Add :ProgramArguments array" \
  -c "Add :ProgramArguments:0 string $HOME/Library/Scripts/LaunchAgents/<readable-task-name>" \
  "$HOME/Library/LaunchAgents/<label>.plist"
```

5. 重新加载并验证。

## 清理失效任务

删除前先确认：

- plist 指向的脚本或 app 已不存在。
- `launchctl list` 中没有正在使用的必要服务。
- 用户确认这个任务可以删除。

删除：

```bash
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/<label>.plist" 2>/dev/null || true
rm "$HOME/Library/LaunchAgents/<label>.plist"
```

删除后验证：

```bash
launchctl list | rg '<label>' || true
```

## 排查要点

- `RunAtLoad=true`：登录或加载时立即运行一次。
- `KeepAlive=true`：进程退出后会被拉起，适合本地服务，不适合普通定时脚本。
- `StartInterval=3600`：每 3600 秒运行一次。
- `StartCalendarInterval`：按日历时间运行，可指定 `Hour`、`Minute`、`Weekday`。
- `WorkingDirectory`：项目脚本依赖相对路径时必须设置。
- `EnvironmentVariables`：写最小必要环境变量。不要把密钥写进 plist；优先让脚本从本机未跟踪配置读取。
- `StandardOutPath` 和 `StandardErrorPath`：必须设置到可写路径，方便排错。

## 输出给用户

完成后简短说明：

- 创建或修改了哪些任务。
- 每个任务的可读名称。
- 是否删除了失效任务。
- 验证结果：`plutil`、`launchctl`、必要时 `sfltool dumpbtm`。

不要把完整 plist 原文贴给用户，除非用户要求。
