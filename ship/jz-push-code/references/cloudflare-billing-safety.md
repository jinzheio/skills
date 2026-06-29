# Cloudflare 账单安全检查

当本次推送涉及新增或修改 Cloudflare 付费资源时，在 push 前逐项检查，防止意外账单。

## 触发条件

先判断本次变更是否涉及 Cloudflare 付费资源。扫描 diff 中的以下信号：

| 信号 | 对应资源 | 典型文件路径 |
|---|---|---|
| `DurableObjectNamespace`、`idFromName`、`state.accept`、`WebSocket` | Durable Objects | `wrangler.*`、`workers/*/src/*` |
| `@cloudflare/d1`、`DB` binding、`drizzle-kit` 指向 D1 | D1 | `wrangler.*`、`drizzle.config.*` |
| `R2Bucket`、`env.R2`、`r2` binding | R2 | `wrangler.*`、`workers/*/src/*` |
| `KVNamespace`、`env.KV` | Workers KV | `wrangler.*` |
| `Queue`、`env.QUEUE` | Queues | `wrangler.*` |
| `WorkerEntrypoint`、`fetch handler`、新 Worker script | Workers | `workers/*/`、`wrangler.*` |
| `images` binding、Images API 调用 | Images | `wrangler.*`、`workers/*/src/*` |
| `ai` binding、`@cloudflare/ai` | Workers AI | `wrangler.*` |
| `browser` binding | Browser Rendering | `wrangler.*` |

如果没有命中以上任何信号，跳过本节，继续后续验证。

## 检查流程

一旦触发，逐项执行。每项标记为 `PASS`、`WARN` 或 `FAIL`。FAIL 项必须向用户报告并等待确认后才能继续 push。

### 1. 计费单位识别

对每个涉及的资源类型，明确它的计费单位：

| 资源 | 计费单位 | 常见放大的路径 |
|---|---|---|
| Durable Objects | duration (GB-s)、requests、storage | 普通 `accept()` 不让 DO hibernation；alarm 循环；storage 写入在循环里 |
| D1 | rows read、rows written、storage | 无索引全表扫描；`WHERE`/`JOIN` 扫大量行 |
| R2 | storage、Class A ops、Class B ops | 无缓存直接打到 bucket；频繁 list/put |
| KV | read/write/delete/list ops | 每请求多次读 KV；用 list 做搜索 |
| Queues | operations | consumer 一直失败反复 retry；producer 无限写入 |
| Workers | requests、CPU time | SSR 把页面请求变 Worker invocation；无鉴权被爬虫打 |
| Images | transformations、stored、delivered | 用户输入导致大量 unique transforms；公开 endpoint 无缓存 |
| Workers AI | tokens（按模型不同） | endpoint 无鉴权；循环调用 |
| Browser Rendering | session duration | 批量页面抓取 |

在 wrangler 配置和 env 里确认是否有免费额度，以及当前计划档次。

### 2. Kill Switch 检查

变更涉及的新 Worker 或修改的 Worker 是否有关闭开关：

- 新增 Worker：检查是否有 `WORKER_DISABLED` 或等价环境变量，入口处是否有判断逻辑
- 修改的 Worker：确认 kill switch 仍然有效
- 没有则标记为 **WARN**，建议代码加：

```js
if (env.WORKER_DISABLED === "true") {
  return new Response("disabled", { status: 503 });
}
```

并在 wrangler vars 中添加 `WORKER_DISABLED`。

### 3. Budget Alert 检查

检查 Cloudflare 账户是否已设置 Budget Alerts：

```bash
# 检查当前账户的账单告警状态（如果能调 API）
curl -s -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/billing/alerts/budget" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f'alerts={len(d.get(\"result\",[]))}')"
```

如果 API 不可用或没有 Budget Alert，标记为 **WARN**，提示用户手动设置：

```text
Manage Account > Billing > Billable Usage > Budget alerts
建议三档：$1 / $5 / $10
```

### 4. 成本监控检查

变更涉及的新资源是否已纳入每小时 GraphQL 成本监控：

- 项目是否已有成本监控脚本（如已部署的 `run_hourly_cost_monitor.sh`）
- 新资源类型是否在监控查询的 dataset 覆盖范围内
- 如果没有监控或新资源未覆盖，标记为 **WARN**，建议上线后添加对应 dataset：
  - DO → `durableObjectsPeriodicGroups`
  - Workers → `workersInvocationsAdaptive`
  - D1 → `d1AnalyticsAdaptiveGroups`
  - R2 → `r2OperationsAdaptiveGroups`
  - KV → `kvOperationsAdaptiveGroups`
  - Queues → `queueConsumersAdaptiveGroups`

### 5. Hibernation 检查（仅 Durable Objects）

如果变更涉及 WebSocket + Durable Object：

- 确认使用 `this.state.acceptWebSocket(server)`，不是 `server.accept()`
- 确认 websocket handler 通过 DO 的 `webSocketMessage()` / `webSocketClose()` / `webSocketError()` 实现
- 确认 notify 逻辑使用 `this.state.getWebSockets()`，不是内存里的 `this.sockets`
- 如果使用了 `server.accept()`，标记为 **FAIL**，要求先改为 WebSocket Hibernation API

参考：[Durable Objects WebSocket Hibernation](https://developers.cloudflare.com/durable-objects/best-practices/websocket-hibernation/)

### 6. 其他常见陷阱速查

| 陷阱 | 检查项 | 严重程度 |
|---|---|---|
| D1 无索引查询 | `EXPLAIN QUERY PLAN` 确认 WHERE/ORDER BY/JOIN 列有索引 | WARN |
| R2 公开文件无缓存 | 对公开 R2 URL，前面是否有 Cloudflare cache | WARN |
| R2 Infrequent Access | 测试环境是否误选了 IA（有最低计费） | WARN |
| Worker 无鉴权 | 新 API endpoint 是否有 auth/rate limit | WARN |
| Worker 无 CPU limit | wrangler 是否配置了 CPU limit | WARN |
| Alarm 无上限 | DO alarm 是否有最大次数/退避/停止条件 | WARN |
| 循环内写入 | storage/KV/D1 写入是否可能在循环/重试中被放大 | WARN |

## 检查报告格式

向用户汇报时：

```markdown
## Cloudflare 账单安全检查

### 涉及的资源
- Durable Objects (clawsimple-runner-notify)
- Workers (clawsimple, staging)

### 检查结果

| # | 检查项 | 结果 | 说明 |
|---|---|---|---|
| 1 | 计费单位 | PASS | DO 按 duration 计费，当前免费额度 400k GB-s/month |
| 2 | Kill Switch | PASS | WORKER_DISABLED 已配置 |
| 3 | Budget Alert | WARN | 未检测到，建议手动设置 $1/$5/$10 |
| 4 | 成本监控 | PASS | 每小时监控已覆盖 |
| 5 | Hibernation | PASS | 已使用 state.acceptWebSocket() |

### 待处理
- Budget Alert 建议 push 后在 Dashboard 手动设置

是否继续 push？
```

## 安全规则

- FAIL 项必须修复后才能 push
- WARN 项报告给用户，由用户决定是否继续
- 不要自动修改 wrangler 配置或 Worker 代码来"修复"问题——只报告，让用户决策
- 如果涉及的变更只是删除或下线资源，可以跳过 2/3/4（kill switch、alert、监控），但 1 和 5 仍然适用
