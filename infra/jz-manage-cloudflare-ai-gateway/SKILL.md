---
name: jz-manage-cloudflare-ai-gateway
description: 查询和配置 Cloudflare AI Gateway。用户要检查 AI Gateway 请求日志、Worker 入口地区、延迟、custom provider、BYOK/auth 方式、spend limit、自定义价格、请求链路，或把 Worker facade 上游接到 AI Gateway 时使用。涉及修改 custom provider、spend limit、gateway 设置或 Worker secret 前先说明影响并验证；不要打印完整 token、provider key 或请求正文。
---

# Cloudflare AI Gateway 运维

## 目标

用于排查和配置 Cloudflare AI Gateway，尤其是这几类问题：

- 某条 LLM 请求走了哪个 provider、model、path。
- AI Gateway 和 Worker 各自的延迟是多少。
- Worker 跑在哪个 Cloudflare colo。
- gateway 是否开启 authentication、spend limits、rate limit、log collection。
- custom provider 的 base URL 是否正确。
- facade 到 AI Gateway 的认证头和 secret 是否正确。
- `cf-aig-custom-cost`、`cf-aig-metadata` 是否进入日志。

默认先做只读查询。涉及修改 Cloudflare、Worker、custom provider 或预算规则时，先确认目标 account/gateway，再操作。

不要输出完整 `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_AI_GATEWAY_TOKEN`、provider API key、student key 或请求正文。需要引用 key 时只说变量名或 secret 名。

## 配置

脚本路径：

```bash
./scripts/cf_ai_gateway_ops.sh
```

脚本读取环境变量的顺序：

1. `JZ_CF_AI_GATEWAY_OPS_ENV` 指向的文件。
2. `~/.config/skills/jz-manage-cloudflare-ai-gateway/.env`。
3. 当前目录的 `.dev.vars`。
4. 当前 shell 已导出的环境变量。

常用变量：

```bash
CLOUDFLARE_ACCOUNT_ID=...
CLOUDFLARE_API_TOKEN=...
CLOUDFLARE_AI_GATEWAY_ID=<gateway-id>
WORKER_NAME=<worker-name>
WORKER_VERSION=<worker-version>
```

`CLOUDFLARE_API_TOKEN` 是 Cloudflare 管理 API token。Worker 调用 AI Gateway 用的 token 通常存为 Worker secret `CLOUDFLARE_AI_GATEWAY_TOKEN`，不要混用。

## 快速命令

在 skill 目录运行：

```bash
./scripts/cf_ai_gateway_ops.sh gateway
./scripts/cf_ai_gateway_ops.sh logs 10
./scripts/cf_ai_gateway_ops.sh log <log_id>
./scripts/cf_ai_gateway_ops.sh spend
./scripts/cf_ai_gateway_ops.sh providers
./scripts/cf_ai_gateway_ops.sh provider <custom-provider-slug>
./scripts/cf_ai_gateway_ops.sh set-provider-base-url <custom-provider-slug> <provider-base-url>
./scripts/cf_ai_gateway_ops.sh worker 2026-06-16T23:33:00Z 2026-06-16T23:38:00Z
./scripts/cf_ai_gateway_ops.sh secrets
```

如果在项目目录有 `.dev.vars`，也可以直接在项目目录运行脚本的绝对路径。

## 查询请求链路

先查最近日志：

```bash
./scripts/cf_ai_gateway_ops.sh logs 10
```

关注字段：

- `created_at`
- `provider`
- `model`
- `path`
- `status_code`
- `duration`
- `tokens_in`
- `tokens_out`
- `cost`
- `custom_cost`
- `metadata`
- `response_content_type`

根据 metadata 判断 facade 映射是否正确：

```json
{
  "key_alias": "<key-alias>",
  "course_model": "<client-model>",
  "upstream_model": "<provider>/<provider-model>",
  "pricing_model": "<pricing-model>"
}
```

单条日志：

```bash
./scripts/cf_ai_gateway_ops.sh log 01KV...
```

默认不要查询或展示 request/response body。即使日志里开启 payload，也只在用户明确要求且确认没有敏感信息时查看。

## 查 Worker 地区和延迟

AI Gateway 日志没有 Worker colo。用 Cloudflare GraphQL 查 Workers analytics：

```bash
./scripts/cf_ai_gateway_ops.sh worker <start_utc> <end_utc>
```

例子：

```bash
./scripts/cf_ai_gateway_ops.sh worker 2026-06-16T23:33:00Z 2026-06-16T23:38:00Z
```

字段解释：

- `coloCode`: Worker 入口地区，例如 `NRT` 是东京。
- `requestDuration`: 端到端请求时长，单位是微秒。
- `wallTime`: Worker 等待 subrequest 的 wall time，单位是微秒。
- `cpuTimeUs`: Worker CPU 时间，单位是微秒。
- `subrequests`: 通常 facade 请求 AI Gateway 是 1。

判断延迟时，把 AI Gateway `duration` 和 Worker `requestDuration` 对比：

- 如果两者接近，慢在 AI Gateway 到上游模型，或模型生成。
- 如果 Worker `requestDuration` 明显更大，可能是 client 到 Worker、stream、代理或连接层问题。
- Worker CPU 通常只有几毫秒；不要把模型生成时间误判成 Worker 计算开销。

Cloudflare GraphQL 聚合有延迟。刚发的请求如果查不到 colo，等一两分钟再查。

## 认证方式

访问 AI Gateway 有两类 token：

1. Cloudflare 管理 API token  
   用于 Cloudflare API，例如查询 gateway、logs、custom providers、spend limits。放在 `CLOUDFLARE_API_TOKEN`。

2. AI Gateway 请求认证 token  
   当 gateway 开启 authentication，Worker 请求 `gateway.ai.cloudflare.com` 时用：

```http
cf-aig-authorization: Bearer <CLOUDFLARE_AI_GATEWAY_TOKEN>
```

不要把它放在 `Authorization`，因为 provider 原生认证也可能需要 `Authorization`。例如 GLM custom provider 要同时有：

```http
authorization: Bearer <GLM_API_KEY>
cf-aig-authorization: Bearer <CLOUDFLARE_AI_GATEWAY_TOKEN>
```

客户端 key 只进入 facade。facade 验证后，再由 Worker 用 AI Gateway token 访问 AI Gateway。

## Custom provider

列出 custom providers：

```bash
./scripts/cf_ai_gateway_ops.sh providers
```

查询一个 slug：

```bash
./scripts/cf_ai_gateway_ops.sh provider <custom-provider-slug>
```

修改 base URL 前先查当前配置。修改后立刻再查，并用真实请求验证。

```bash
./scripts/cf_ai_gateway_ops.sh set-provider-base-url <custom-provider-slug> <provider-base-url>
./scripts/cf_ai_gateway_ops.sh provider <custom-provider-slug>
```

provider-specific custom provider 路径：

```text
slug: <custom-provider-slug>
base_url: <provider-base-url>
gateway endpoint:
https://gateway.ai.cloudflare.com/v1/<account>/<gateway>/custom-<custom-provider-slug>/<provider-path>
body model:
<provider-model>
```

注意：provider-specific endpoint 会把 `custom-<slug>/` 后面的路径追加到 custom provider 的 `base_url` 后面。上面的路径最终转到：

```text
<provider-base-url>/<provider-path>
```

## 协议转换 reference

需要检查或切换 facade 的上游协议时，读取 `references/facade-protocol-switching.md`。

这份 reference 只记录通用做法：

- OpenAI 兼容和 Anthropic 原生路径的区别。
- provider-specific endpoint 的 URL 结构。
- 用 Worker env var 或代码常量控制哪些 provider 走 Anthropic 原生。
- Kimi、DeepSeek 等 provider 的参数和统计差异。
- 修改后如何用测试请求和 AI Gateway logs 验证。

不要把具体 Worker 名、域名、gateway id、key alias、token 来源、服务器路径或课程部署信息写进 skill repo。需要举例时使用 `<worker-name>`、`<gateway-id>`、`<client-base-url>`、`<client-model>`、`<provider-model>`。

## Spend limits 和 custom cost

查 gateway 配置：

```bash
./scripts/cf_ai_gateway_ops.sh gateway
```

如果 per-gateway spend limits 已设置，通常会看到：

```json
"spend_limits": {
  "enabled": true,
  "rules": [
    {
      "limitType": "cost",
      "limit": 30,
      "window": 86400,
      "technique": "fixed"
    }
  ]
}
```

账号级 Unified Billing spend limit 不是同一件事。API 路径 `/ai-gateway/billing/spending-limit` 可能返回 `NO_MANUAL_TOPUP`，这不代表 per-gateway spend limit 不可用。

`cf-aig-custom-cost` 只定义单价。AI Gateway 还需要上游响应里的 token usage 才能计算成本：

```text
cost = input_tokens * per_token_in + output_tokens * per_token_out
```

如果上游不返回 usage，custom cost 和 spend limit 可能无法准确生效。

## 修改前检查

修改 gateway、custom provider、Worker secret 或 budget 前：

1. 确认 `CLOUDFLARE_ACCOUNT_ID` 和 gateway id。
2. 查当前配置并保存关键字段到操作记录。
3. 确认 token 权限，通常至少需要 AI Gateway Read/Write；Worker secret 或部署还需要 Workers 相关权限。
4. 修改后重新查询配置。
5. 发一条真实请求。
6. 查 AI Gateway logs，确认 provider、model、path、status、duration、tokens、cost、metadata。
7. 查 Worker analytics，确认 colo 和 requestDuration。

不要因为 Dashboard 显示延迟或日志缺失就立刻下结论。Cloudflare 日志和 GraphQL 聚合都可能延迟。
