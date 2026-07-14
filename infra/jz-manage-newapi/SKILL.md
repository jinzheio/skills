---
name: jz-manage-newapi
description: 查询和运维 New API 服务。用户要查 New API 模型列表、渠道、SQLite 表、token/user 额度、每日额度 cron、fallback 渠道、Docker/Nginx 状态、最近日志，或要求配置 New API fallback、设置总额度、设置每日额度、检查 cc-switch/Claude Code 接入格式时使用。默认只读；修改生产 New API 前必须备份 SQLite，并在重启后验证。
---

# New API 运维

## 目标

用于管理 New API 服务，不要和 LiteLLM 混用。

仓库是 public repo。不要把主机名、公网 IP、Tailscale IP、模型列表、provider key、token、业务 fallback 规则写进 skill 文件。私有配置放在：

```text
~/.config/skills/jz-manage-newapi/
```

New API 没有 LiteLLM 的 `router_settings.fallbacks`。它通常用多个渠道承接同一个模型名，再用 `priority` 和失败重试实现 fallback。

## 配置

脚本路径：

```bash
./scripts/newapi_ops.sh
```

脚本默认读取：

```text
~/.config/skills/jz-manage-newapi/.env
~/.config/skills/jz-manage-newapi/fallback-plan.json
```

`.env` 示例：

```bash
NEWAPI_SSH_HOST=your-ssh-host
NEWAPI_SSH_USER=
NEWAPI_SSH_PORT=22
NEWAPI_REMOTE_DIR=<newapi-dir>
NEWAPI_DB=<newapi-dir>/data/one-api.db
NEWAPI_PUBLIC_BASE=http://host-or-domain:3000/v1
NEWAPI_TAILSCALE_UI=http://tailnet-host:3001
NEWAPI_LOCAL_UI=http://127.0.0.1:3001
NEWAPI_API_KEY_ENV_FILE=/path/to/project/.env
NEWAPI_API_KEY_ENV_NAME=LITELLM_LONG_RUN_KEY
NEWAPI_MANAGED_TAG=managed
NEWAPI_FALLBACK_TAG=fallback-generated
NEWAPI_MODEL_NAME_FILTER=model-%
NEWAPI_PREFER_ANTHROPIC_MODELS=model-a,model-b
```

`fallback-plan.json` 示例：

```json
{
  "managed_tag": "managed",
  "generated_tag": "fallback-generated",
  "retry_times": 3,
  "primary": [
    {
      "channel": "primary-channel-name",
      "models": "model-a,model-b",
      "model_mapping": {
        "model-a": "upstream-a",
        "model-b": "upstream-b"
      },
      "priority": 100,
      "weight": 10
    }
  ],
  "fallbacks": [
    {
      "model": "model-a",
      "routes": [
        {
          "source_channel": "fallback-channel-name",
          "name": "model-a-fallback-provider",
          "model_mapping": {
            "model-a": "fallback-upstream"
          },
          "priority": 90
        }
      ]
    }
  ]
}
```

不要输出完整 token、provider key、New API token、Nginx key rewrite 里的完整 key。

## 常用命令

```bash
# Docker、端口、UI 状态
./scripts/newapi_ops.sh status

# 公网 /v1/models
./scripts/newapi_ops.sh models

# 渠道和模型映射
./scripts/newapi_ops.sh channels

# token/user 额度和每日重置 cron
./scripts/newapi_ops.sh quotas

# 以渠道 priority 形式展示 fallback
./scripts/newapi_ops.sh fallback

# 最近请求日志
./scripts/newapi_ops.sh logs

# 按 fallback-plan.json 重新应用 fallback
./scripts/newapi_ops.sh apply-fallback-plan

# 只渲染 fallback SQL，不写数据库
./scripts/newapi_ops.sh render-fallback-sql

# 设置用户总额度，单位 USD
./scripts/newapi_ops.sh set-total-quota <user_id> <usd>

# 设置 token 每日额度 cron，单位 USD
./scripts/newapi_ops.sh set-daily-quota-cron <token_id> <usd>

# 比较 Anthropic Messages 和 OpenAI chat 路径
./scripts/newapi_ops.sh compare-formats <model>
```

## 操作规则

先判断用户意图。

只读查询：

- 当前可填写模型。
- 各模型上游映射。
- fallback 是否配置。
- token 剩余额度、总额度、每日额度是否存在。
- UI 或公网 API 是否可用。
- 某次请求落到了哪个上游模型。
- cc-switch / Claude Code 当前走 `/v1/messages` 还是 `/v1/chat/completions`。

修改操作：

- 改 fallback。
- 改总额度。
- 改每日额度 cron。
- 改渠道、模型映射、价格。

修改前必须备份 SQLite：

```bash
cd "$NEWAPI_REMOTE_DIR"
cp data/one-api.db "data/one-api.db.before-change-$(date +%Y%m%d-%H%M%S)"
```

修改后必须：

1. 查询 SQLite，确认字段已写入。
2. 重启 `new-api` 容器。
3. 验证 `/v1/models`。
4. 至少做一个轻量请求或查最近 `logs`。
5. 汇报备份文件、改动、验证结果和失败项。

## 额度

New API 当前常见版本不原生支持每日额度字段。

它原生支持：

- `users.quota`：用户总额度。
- `users.used_quota`：用户已用额度。
- `tokens.remain_quota`：token 当前剩余额度。
- `tokens.used_quota`：token 已用额度。
- `tokens.unlimited_quota`：是否无限额度。
- `tokens.model_limits`：token 可用模型列表。

常见换算关系：

```text
$1 = 500000 quota
```

每日额度用 cron 实现：

```text
5 0 * * * <newapi-dir>/reset-token-<token-id>-quota.sh >> <newapi-dir>/logs/quota-reset.log 2>&1
```

脚本每天把指定 token 的 `remain_quota` 补到每日额度。如果用户总额度少于每日额度，只放出剩余总额度。

## Fallback

用 `fallback-plan.json` 管 fallback，不要把业务模型名写进 `SKILL.md` 或脚本。

应用规则：

1. 读取 `managed_tag` 和 `generated_tag`。
2. 删除旧的 `generated_tag` 渠道。
3. 更新 `primary` 里的主渠道模型列表、映射、优先级和权重。
4. 按 `fallbacks[].routes[]` 从已有主渠道复制 key/base_url/type 等字段，生成只承接指定模型名的新渠道。
5. 写入 `RetryTimes`。
6. 重启 New API 并查询渠道表。

如果某个模型不应该 fallback，就不要在 `fallbacks` 里给它配置 routes。

## cc-switch / Claude Code

Claude Code 原生使用 Anthropic Messages。给 cc-switch / Claude Code 配 New API provider 时，优先让可兼容的模型走 Anthropic 路径：

```json
{
  "apiFormat": "anthropic"
}
```

原因：

- OpenAI 兼容路径通常需要 cc-switch 把 Anthropic 请求转成 OpenAI chat，再把响应转回 Claude 可读格式。
- 一些上游的 OpenAI endpoint 会先输出 reasoning token；`max_tokens` 太小时可能出现正文为空。
- 比较延迟时，不只看客户端 wall time，也要看 New API 日志里的 `request_path`、`request_conversion`、`frt`、`use_time`、`prompt_tokens`、`completion_tokens`、`cache_tokens` 和 `upstream_model_name`。

排查时运行：

```bash
./scripts/newapi_ops.sh compare-formats <model>
./scripts/newapi_ops.sh logs
```

如果日志里目标模型主要走 `/v1/chat/completions`，而该模型支持 Anthropic Messages，优先改 cc-switch provider 配置。

## 日志

看请求最终使用了哪个上游模型：

```sql
select id, model_name, channel_id, substr(other, 1, 1000)
from logs
order by id desc
limit 20;
```

重点看：

- `channel_id`
- `channel_name`
- `use_channel`
- `upstream_model_name`
- `request_path`
- `request_conversion`
- `frt`
- `use_time`
- `status`

默认不要 push、发布或改其它服务。New API 与 LiteLLM 独立，除非用户明确要求，不要查询或修改 LiteLLM。
