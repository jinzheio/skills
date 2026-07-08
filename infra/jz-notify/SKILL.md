---
name: jz-notify
description: 为 agent、定时任务和本机脚本发送完成通知。需要发 macOS/Linux 系统通知、飞书消息（lark-cli 或带签名 webhook）、Slack 消息（Codex Slack connector 优先，webhook 兜底），或为项目接入统一通知脚本时使用。
---

# 通知发送

用于把任务完成、失败、需要人工处理等状态发到三类通道：

- 本机系统通知：macOS `osascript`，Linux `notify-send` 或 `wall`。
- 飞书：优先 `lark-cli im +messages-send`，失败时用 webhook；支持签名校验。
- Slack：在 Codex 会话里优先用 Slack connector；脚本保留 incoming webhook 兜底。

不要把 webhook、sign key、token、真实群名、联系人或客户名写进 repo。配置只放本机未跟踪目录。

## 配置

默认配置文件：

```text
~/.config/skills/jz-notify/.env
```

也可用 `JZ_NOTIFY_ENV` 指向其它配置文件。脚本读取优先级：

1. `JZ_NOTIFY_ENV` 指向的文件。
2. `~/.config/skills/jz-notify/.env`。
3. 当前 shell 已导出的环境变量。

可用变量：

```bash
# 飞书 CLI 目标，二选一。chat id 优先。
LARK_CHAT_ID=oc_xxx
FEISHU_CHAT_ID=oc_xxx
LARK_USER_ID=ou_xxx
FEISHU_USER_ID=ou_xxx
LARK_SEND_AS=bot

# 飞书 webhook 兜底；开启签名校验时填 sign key。
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
LARK_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_SIGN_KEY=xxx
FEISHU_WEBHOOK_SECRET=xxx
LARK_SIGN_KEY=xxx
LARK_WEBHOOK_SECRET=xxx

# 强制飞书只走 webhook，用于测试。
FEISHU_NOTIFY_METHOD=webhook

# Slack。Codex 中优先使用 connector，channel 从配置读取。
SLACK_CHANNEL_ID=C...
SLACK_CHANNEL_NAME=<channel-name>

# Slack webhook 兜底。脚本或非 Codex 环境使用。
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
SLACK_USER_ID=U...
```

## 快速发送

在 skill 目录内运行：

```bash
./scripts/notify.sh "任务完成" "已生成结果，等待检查"
```

脚本会：

1. 发本机系统通知。
2. 发飞书：默认先 `lark-cli`，失败再 webhook。
3. 发 Slack webhook（如果配置了 `SLACK_WEBHOOK_URL`）。

测试飞书 webhook 签名：

```bash
FEISHU_NOTIFY_METHOD=webhook ./scripts/notify.sh "通知测试" "飞书 webhook 签名路径"
```

## Codex Slack Connector

如果当前环境有 Slack connector，发 Slack 时先读取配置文件，再用 connector 发送：

```text
mcp__codex_apps__slack._slack_send_message
```

- `channel_id` 优先取 `SLACK_CHANNEL_ID`。
- 如果没有 `SLACK_CHANNEL_ID`，但有 `SLACK_CHANNEL_NAME`，先用 Slack connector 查频道，再发送。
- 如果配置的是 `SLACK_USER_ID`，可直接作为 DM 的 `channel_id`。
- 消息内容用同一份标题和正文，保持和飞书通知一致。
- 如果 Slack connector 不可用，再用 `SLACK_WEBHOOK_URL` 兜底。

## 接入项目

推荐把脚本作为外部 skill 调用，不复制到业务项目：

```bash
<skill-dir>/scripts/notify.sh "素材卡就绪" "共 8 张卡，缺图 1 张"
```

如果业务项目必须自带脚本，可复制 `scripts/notify.sh`，但仍使用 `~/.config/skills/jz-notify/.env` 或 `JZ_NOTIFY_ENV` 管理配置。

通知失败不能覆盖主任务结果。脚本会把失败写到 stderr，并保持退出码为 0，避免通知通道短暂故障导致定时任务被判失败。

## 排查

- 飞书 CLI 失败：先看 `lark-cli auth status --json`，确认 bot 或 user 可用。
- bot 不能发给某人：确认飞书应用的可用范围包含该用户，或改发到已加入 bot 的群。
- webhook 签名失败：确认 `FEISHU_SIGN_KEY` 与群机器人设置一致；用 `FEISHU_NOTIFY_METHOD=webhook` 强制测试。
- Slack connector 不可用：检查 Codex 是否已连接 Slack；脚本或定时任务环境用 `SLACK_WEBHOOK_URL`。
