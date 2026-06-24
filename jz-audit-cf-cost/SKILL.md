---
name: jz-audit-cf-cost
description: "当需要在某个 Cloudflare Workers/Pages 项目中读取、解释或核对 Cloudflare 账单、usage、计费周期费用、运行中资源成本时使用。适用于从当前项目的 wrangler 配置、package.json、源码引用、.dev.vars 或 .env 认证字段识别资源，并用 Cloudflare GraphQL schema/probe、PayGo usage、手工 quota 输入或本地估算核对 Durable Objects/Workers/D1/R2/KV/Queues/Images/Workers AI 等付费资源和异常计费。也适用于审计 Cloudflare D1 rows read 异常、SQL 查询计划、未加索引的全表扫描、公开页面实时聚合查询和 D1 索引设计风险。"
---

# Cloudflare 账单核算

用于在具体项目目录里核对 Cloudflare 当前账期用量，找出已经产生或可能产生费用的资源。

## 默认口径

- 默认从当前工作目录开始向上查找项目根；用户指定项目路径时再传 `--project <repo-root>`。
- 默认读取项目根目录的 `.dev.vars`、`.env`、`.env.local` 里的 Cloudflare 凭据，再回退到进程环境变量；Account ID 也可以从 Wrangler 配置的 `account_id` 读取。
- 用户没有指定日期时，默认查当前计费周期。
- PayGo usage API 不传 `from` / `to`，让 Cloudflare 返回当前 billing period。
- GraphQL Analytics API 没有统一的账期端点。脚本只做 schema discovery 和 dataset probe，默认用 UTC 当月 1 日到明天作为 analytics window；报告时说明它不是 invoice 口径。
- GraphQL probe 用来确认哪些 dataset 当前账号可查；PayGo usage、手工 quota 输入或用户提供的 Dashboard Billable Usage 数字用来对账。
- API 返回 raw usage 或只返回 dataset 可查性时，不要把它解释成完整账单；只报告数据能支撑的结论。

## 执行流程

### 1. 识别资源

先运行脚本读取项目配置和代码引用：

```bash
node <skill-dir>/scripts/audit-cf-usage.mjs \
  --dry-run
```

如果不在目标项目目录运行，再传项目路径：

```bash
node <skill-dir>/scripts/audit-cf-usage.mjs \
  --project <repo-root> \
  --dry-run
```

脚本会读取 `wrangler.toml`、`wrangler.json`、`wrangler.jsonc`，并识别：

- Workers / Pages Functions
- KV
- D1
- R2
- Durable Objects
- Queues
- cron triggers
- Workers AI binding 或 `env.AI` / `AI.run`
- Images binding、`/cdn-cgi/image/`、Worker image transforms、外部 `images.*` host 引用

如果资源只写在 Wrangler 的 `env.<name>` 环境配置里，脚本仍要识别，并在资源上标注 `environment`。

如果项目没有 wrangler 配置，但 `package.json` 显示它使用 Cloudflare adapter、Wrangler 或 deploy script，仍按 Workers 项目处理，并标注来源是 `package.json`。

dry-run 也会输出 `riskFindings`。这些不是已确认 bug，而是需要人工确认的成本放大路径：

- Queue consumer 调用自己的公开 API，并把用户侧 `write_mode` / `writeMode` 继续传进去。
- 同一个 Durable Object 文件里出现多处 `storage.put()`，尤其是状态流转、ack、mirror 写入。
- API key、auth、legacy fallback 路径里出现 KV `list()`。
- Wrangler 同时包含 Queues、Durable Objects 和 KV。
- 项目使用 D1，且用户问到 rows read、全表扫描、索引、查询计划、公开统计页或 D1 成本异常。

### 2. 读取凭据

脚本会按顺序读取：

1. `--env-file <path>` 指定的文件
2. 项目根目录 `.dev.vars`
3. 项目根目录 `.env`
4. 项目根目录 `.env.local`
5. 当前进程环境变量
6. Wrangler 配置里的 `account_id`（只用于 Account ID）

支持的字段名：

- Account ID：`CLOUDFLARE_ACCOUNT_ID`、`CF_ACCOUNT_ID`
- API token：`CLOUDFLARE_API_TOKEN`、`CF_API_TOKEN`

不要在命令行参数里传 API token，避免进入 shell history 或进程列表。报告里也不要输出 token、env 文件路径里的本机绝对路径或账号原值。

资源识别时不要输出 KV namespace id、D1 database_id、account id 这类真实 ID。只说明资源名、binding、环境名和 `idPresent` / `databaseIdPresent`。

### 3. 查 API

有 Cloudflare 凭据时运行：

```bash
node <skill-dir>/scripts/audit-cf-usage.mjs
```

需要权限：

- GraphQL Analytics：`Account: Analytics: Read`
- PayGo usage：该 API 目前是 alpha，可能还需要账号 billing 权限；如果返回 404、403 或 unavailable，不要记成 `$0`

用户指定日期时再传：

```bash
node <skill-dir>/scripts/audit-cf-usage.mjs \
  --from 2026-06-01 \
  --to 2026-06-16
```

### 4. 覆盖范围

| 项目 | 监控方式 | 备注 |
|---|---|---|
| Workers / Pages Functions | GraphQL Workers dataset probe；PayGo / quota rows 对账 | 看 requests、CPU time |
| KV operations | GraphQL `kvOperationsAdaptiveGroups` probe；quota rows 对账 | 看 read/write/delete/list |
| KV storage | GraphQL `kvStorageAdaptiveGroups` probe；quota rows 对账 | 估算 GB-month |
| D1 | GraphQL `d1AnalyticsAdaptiveGroups` / storage dataset probe；quota rows 对账 | 看 rows read、rows written、storage |
| R2 Class A / B | GraphQL `r2OperationsAdaptiveGroups` probe；quota rows 对账 | 看 Class A / Class B operations |
| R2 storage | GraphQL `r2StorageAdaptiveGroups` probe；PayGo / quota rows 对账 | R2 按每日 peak storage 平均成 GB-month |
| Images transform | GraphQL Images 相关 dataset probe；PayGo / quota rows 对账 | 看 unique transformations、stored、delivered |
| Workers AI | GraphQL Workers AI / AI inference dataset probe；PayGo / quota rows 对账 | 账单口径是 Neurons |
| Cron Triggers | Workers scheduled event / invocation dataset probe | Cron 本身不是独立计费项，通常落到 Workers requests 和 CPU time |
| Queues | GraphQL Queues dataset probe；quota rows 对账 | 看 operations；retry 会增加 read operations |
| Durable Objects | 本地估算、PayGo / quota rows 对账 | 看 duration、requests、storage rows written |

Cloudflare GraphQL schema 会变。实际查询前先用脚本做 schema discovery，确认当前账号里存在的 dataset 和字段。脚本会根据 filter input 字段选择 `date_geq/date_lt` 或 `datetime_geq/datetime_lt`。

### 5. 输出

报告时优先使用脚本输出的 `usageRows`。不要重新解释 raw PayGo JSON，除非 `usageRows` 缺少用户明确要看的字段。

每个 `usageRows[]` 项固定包含这些字段：

| 字段 | 含义 |
|---|---|
| `product` | Cloudflare 产品名 |
| `metric` | 计费或用量指标 |
| `source` | 数据来源，例如 `manual-quota`、`local-estimate`、`paygo-usage` |
| `sourceDetail` | 来源细节；只能写相对文件、dataset 或本地估算参数 |
| `period` | `monthly`、`daily` 或 `null` |
| `used` / `unit` | 当前用量和单位 |
| `included` | plan 内额度；未知时为 `null` |
| `billableUsed` | 扣除额度后的计费用量；未知时为 `null` |
| `projectedUsed` | 账期末或每日外推用量；未知时为 `null` |
| `usedPlanRatio` | 已用占 plan 内额度比例；未知时为 `null` |
| `projectedPlanRatio` | 外推占 plan 内额度比例；未知时为 `null` |
| `estimatedCostUsd` | 当前估算费用；未知时为 `null` |
| `projectedCostUsd` | 外推估算费用；未知时为 `null` |
| `confidence` | `high`、`medium` 或 `low` |
| `note` | 需要保留的不确定性说明 |

如果输出包含 `datasetProbes`，只把它当作“当前账号 schema 中这个 dataset 可以查询”的证据。它不能替代 `usageRows`，也不能证明费用是 `$0`。

如果输出包含 `riskFindings`，先按 `severity` 从高到低看。高风险项需要读对应源码，确认是否在请求热路径、queue consumer 或 auth fallback 中触发。

报告时只写能支撑判断的数字：

- 查询范围和数据来源
- 识别到的付费资源
- 每个产品的用量、plan 内额度、计费用量、预估费用
- 已用占 plan 内额度比例
- 外推到当前计费周期结束时，占 plan 内额度比例
- 当前账期累计费用；如果只能拿到 GraphQL analytics，标注为估算
- 月末预测
- 需要立即处理的异常项

结果报告必须包含这两列：

| 字段 | 计算 |
|---|---|
| 已用占 plan 内额度比例 | `当前已用量 / plan 内额度` |
| 账期末外推比例 | `(当前已用量 / 已过账期天数 × 当前账期总天数) / plan 内额度` |

常见计费项都要计算比例，不要只算 Durable Objects。至少覆盖本次项目中识别到的 Workers requests / CPU、KV operations / storage、D1 rows / storage、R2 Class A / Class B / storage、Images transformations、Workers AI、Queues operations 和 Durable Objects duration。

如果额度每天重新计，外推不要用账期累计量。使用最近 3 天平均用量：

```text
每日额度项目的账期末外推比例 = 最近 3 天日均用量 / 每日 plan 内额度
```

这类项目的“已用占 plan 内额度比例”使用今天或最近一个完整日的用量除以每日额度。没有日粒度数据时，保留比例列，值写 `未知`，说明缺少最近 3 天日用量。

如果某个产品没有 plan 内额度，或 API 没返回额度，仍保留这两列，值写 `未知`，并说明缺少哪个字段。不要省略。

如果某个 API 返回 `Costs not found`、404、403 或 unavailable，只说明不可查，不要写成 `$0`。

`paygo-usage` 来源的 `usageRows` 是从 Cloudflare raw response 中保守抽取的行，默认 `confidence` 是 `low`。除非字段名和用户提供的 Dashboard/receipt 数字能对上，不要把它当最终 invoice。

### 6. 额度比例计算

GraphQL 或 PayGo 拿到用量后，用脚本统一计算比例。月度额度示例：

```bash
node <skill-dir>/scripts/audit-cf-usage.mjs \
  --quota "product=KV,metric=reads,used=1200000,included=10000000,period=monthly,elapsedDays=15,cycleDays=30,unit=ops" \
  --dry-run
```

每日重置额度示例：

```bash
node <skill-dir>/scripts/audit-cf-usage.mjs \
  --quota "product=KV,metric=reads,used=70000,included=100000,period=daily,last3=60000|70000|80000,unit=ops" \
  --dry-run
```

也可以把多个计费项写入 JSON：

```json
[
  {
    "product": "KV",
    "metric": "reads",
    "used": 1200000,
    "included": 10000000,
    "period": "monthly",
    "elapsedDays": 15,
    "cycleDays": 30,
    "unit": "ops"
  },
  {
    "product": "Images",
    "metric": "transformations",
    "used": 4200,
    "included": 5000,
    "period": "monthly",
    "elapsedDays": 15,
    "cycleDays": 30,
    "unit": "unique transformations"
  },
  {
    "product": "Workers",
    "metric": "requests",
    "used": 70000,
    "included": 100000,
    "period": "daily",
    "last3": [60000, 70000, 80000],
    "unit": "requests"
  }
]
```

```bash
node <skill-dir>/scripts/audit-cf-usage.mjs \
  --quota-json ./cf-usage-items.json \
  --dry-run
```

需要在没有 API 数据时估算 Durable Objects duration，可以使用：

```bash
node <skill-dir>/scripts/audit-cf-usage.mjs \
  --estimate-do \
  --do-objects 5 \
  --do-hours-per-day 24 \
  --do-days 30 \
  --do-memory-mb 128 \
  --dry-run
```

脚本会输出 duration GB-s、扣除免费额度后的 billable GB-s 和估算费用。

## 什么时候读 reference

只有在识别到某个产品已经产生费用、即将产生费用，或用户要求给排查建议时，才读取 `references/cost-advice.md` 的相关段落。不要在正常核账流程里先读建议材料。

当项目使用 D1，且出现以下任一情况时，读取 `references/d1-full-scan-audit.md`：

- Cloudflare usage 或用户提供的数据里 D1 rows read 异常。
- 用户明确要求确认 D1 是否有全表扫描、缺索引、查询计划或 rows read 风险。
- 公开页面、API、Cron、Queue consumer、Webhook、Analytics 页面里有实时 D1 查询。
- 准备上线新的 D1 查询或 migration，需要判断索引是否覆盖热路径。
