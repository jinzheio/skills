---
name: jz-check-metrics
version: "1.0.0"
description: "实时查看站点 metrics。覆盖 Google Search Console、Cloudflare Analytics、Umami、Microsoft Clarity 四个 provider。未指定域名时自动从项目配置中检测。需要查看站点表现、搜索数据、流量、用户行为时触发。触发词包括 '查一下网站的 metrics'、'查看站点数据'、'最近表现怎么样'。默认获取全部 provider。"
---

# 站点 Metrics 实时查看

实时调用各 provider API 获取当前数据，返回结构化结果。**只读，不写任何文件。**

## 触发条件

- 查看 GSC / Search Console 数据、搜索表现、排名
- 查看 Cloudflare 流量、访问量
- 查看 Umami 统计数据
- 查看 Clarity 用户行为数据
- 查看站点 metrics / analytics
- "帮我看看 XX 的数据"、"XX 最近表现怎么样"
- "查一下网站的 metrics"、"查一下 metrics"

## 前置条件

- Python 3 + `requests`（`uv pip install requests` 如缺失）
- Google ADC 已认证（`gcloud auth application-default login`），用于 GSC
- 各 provider 凭据在 `~/.config/skills/jz-check-metrics/.env`（本机）或 skill 根目录 `.env`（fallback）

## 输入

- 可选：`--hostname`，例如 `growagardencalculate.com`。未指定时，自动从当前项目配置文件读取。
- 可选：`--days`（默认 28）
- 可选：`--providers` 逗号分隔，默认 `gsc,cloudflare,umami,clarity`。可选值：`gsc` | `cloudflare` | `umami` | `clarity`

## 站点自动发现（Hostname 自动检测）

当用户未提供 `--hostname` 时，按以下优先级从当前项目读取：

1. `wrangler.jsonc` / `wrangler.toml`：`routes[].pattern`（取 `custom_domain: true` 的条目，优先 apex 域名，去掉 `www.`）
2. `.env.local` / `.env`：`NEXT_PUBLIC_BASE_URL`、`NEXT_PUBLIC_SITE_URL`、`SITE_URL`、`BASE_URL`
3. `next.config.ts` / `next.config.js` / `next.config.mjs` 中显式配置的域名
4. `package.json`：`homepage` 字段
5. `src/app/layout.tsx` / `app/layout.tsx` 等：代码中硬编码的 `baseUrl` / `siteUrl`
6. `.vercel/project.json`：仅作参考，通常只含 `projectName` 不含完整域名

读取到候选 hostname 后：

- 清理协议头（`https://`）、`www.`、路径、尾部斜杠、端口，统一小写
- 过滤掉 `localhost`、`127.0.0.1` 等本地地址
- 向用户确认："检测到站点 `{hostname}`，是否使用该站点？回复其它域名可切换，回复 `n` 可取消。30 秒内无反馈将自动继续。"
- **30 秒超时处理**：若用户在 30 秒内未反馈，自动按确认继续（使用检测到的 hostname）
- 若用户回复其它域名，使用用户提供的域名
- 若检测到多个候选域名，列出让用户选择

如果未检测到任何 hostname，提示用户手动输入：
`未检测到站点域名，请提供 --hostname，例如 auditmycareer.com`

## 流程

1. 解析参数：若 `--hostname` 为空，执行站点自动发现
2. 确认检测到的 hostname，或等待 30 秒超时
3. 加载凭据：先读 `~/.config/skills/jz-check-metrics/.env`，缺失的变量 fallback 到 skill 根目录 `.env`
4. **先跑脚本**：`python3 <skill-dir>/scripts/check_metrics.py --hostname <hostname> --days <N> --providers gsc,cloudflare,umami,clarity`
5. **逐 provider 检查结果**：脚本输出为 JSON，遍历 `.providers` 和 `.errors` 中每个 provider
6. **任何 provider 失败，必须尝试 fallback 后继续**：见下方 fallback 策略
7. 汇总输出，标注每个 provider 的成功/失败状态和使用的获取方式

## 完整性保证（CRITICAL）

**无论如何不能遗漏任何 provider。** 即使脚本失败，也必须按自然语言逐个 provider 做 fallback 获取。汇报时必须列出全部 4 个 provider，每个标注实际状态。没有例外。

### Fallback 策略

当脚本对某个 provider 报错时，按以下优先级手动获取：

**Umami fallback**：直接用 `curl` 调 API。
```bash
# 1. 从 env 文件读凭据
grep UMAMI ~/.config/skills/jz-check-metrics/.env
# 2. 登录获取 token
curl -s -X POST "$UMAMI_BASE_URL/api/auth/login" -H "Content-Type: application/json" \
  -d '{"username":"...","password":"..."}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])"
# 3. 获取 website ID
curl -s "$UMAMI_BASE_URL/api/websites" -H "Authorization: Bearer $TOKEN"
# 4. 获取 stats
curl -s "$UMAMI_BASE_URL/api/websites/$ID/stats?startAt=$START&endAt=$END" -H "Authorization: Bearer $TOKEN"
# 5. 获取 pageviews 序列和常用 metrics（referrer/path/browser/device/country）
```

**Cloudflare fallback**：
1. 如果 SSL 被阻断，直接用 `curl` 轮询 `api.cloudflare.com`；如仍失败，标记为网络不可达并说明原因（如 GFW 阻断）。
2. 如果报错提示免费版 zone 只能查询 7 天内数据（`cannot request data older than 1w1d`），将 `--days` 降到 7 重新获取，并在汇报中注明这是 7 天 fallback 数据。

**GSC fallback**：如果 ADC 失败，检查 `gcloud auth application-default login` 是否过期，提示用户重新认证。

**Clarity fallback**：
1. 如果 SSL 不稳定，重试 3 次间隔 2s；如仍部分维度失败，已获取的 summary 数据仍然汇报。
2. 如果提示 token 缺失，检查 `~/.config/skills/jz-check-metrics/site-integrations.json` 是否存在并按 hostname 匹配。

### 汇报模板

最终汇报必须按此格式，4 个 provider 全部列出：

```
## {hostname} · 最近 {days} 天

### ✅/❌ Google Search Console — {状态}
关键指标...

### ✅/❌ Cloudflare Analytics — {状态}
关键指标...（或错误原因）

### ✅/❌ Umami — {状态}
关键指标...（或错误原因）

### ✅/❌ Microsoft Clarity — {状态}
关键指标...（或错误原因）
```

不能出现"只有 Umami 数据"或其它不完整的汇报。

## Provider 详情

### Google Search Console (`gsc`)

通过 ADC OAuth 获取 access token，调 Search Console API：

- `sites.list` → 匹配 `sc-domain:<hostname>` property
- `searchAnalytics.query` → 获取：
  - 按日期维度：每日 clicks/impressions/ctr/position
  - 按 query 维度：热门搜索查询
  - 按 page 维度：热门页面
- 汇总：总 clicks、总 impressions、平均 CTR、平均 position

凭据：ADC（`gcloud auth application-default print-access-token`），quota project 从 env `GCP_QUOTA_PROJECT`。

### Cloudflare Analytics (`cloudflare`)

通过 Cloudflare GraphQL API 获取：

- 按小时的时间序列（requests、visits、edgeResponseBytes）
- 热门路径 top 10
- 汇总 totals

凭据：`CLOUDFLARE_ANALYTICS_API_TOKEN`（优先），fallback `CLOUDFLARE_API_TOKEN`。

### Umami (`umami`)

通过 Umami API 获取：

- 站点 stats（pageviews、visitors、visits、bounces）
- 按天的 pageviews 序列
- metrics breakdown：referrer、path、browser、device、country

凭据：`UMAMI_API_KEY`（优先），fallback 用 `UMAMI_ADMIN_USERNAME` + `UMAMI_ADMIN_PASSWORD` 登录获取 bearer token。`UMAMI_BASE_URL` 指定 API 地址。

### Microsoft Clarity (`clarity`)

通过 Clarity Export API 获取：

- 项目 summary
- 维度 breakdown：Browser、Device、Country/Region、Source、URL

凭据：`CLARITY_EXPORT_TOKEN`（全局 fallback），或从 `site-integrations.json` 按 hostname 匹配。优先查找路径：

- `~/.config/skills/jz-check-metrics/site-integrations.json`
- 环境变量 `SITE_INTEGRATIONS_CONFIG` 指定的路径

## 凭据加载

```bash
# 本机凭据（优先）
~/.config/skills/jz-check-metrics/.env

# fallback
<skill-dir>/.env
```

`~/.config/skills/jz-check-metrics/.env` 已 `.gitignore`，不会被提交。

## 脚本

脚本嵌入在 skill 中，不依赖外部仓库。`--hostname` 未提供时会自动从项目配置中检测。

调用方式：
```bash
python3 <skill-dir>/scripts/check_metrics.py \
  --hostname growagardencalculate.com \
  --days 28 \
  --providers gsc,cloudflare,umami,clarity
```

或省略 hostname（自动检测）：
```bash
python3 <skill-dir>/scripts/check_metrics.py \
  --days 28 \
  --providers gsc,cloudflare,umami,clarity
```

## 完成汇报

按 provider 列出。必须覆盖全部 4 个 provider，缺一不可：

- `success` / `partial` / `error` — 数据获取状态
- 失败时写清原因和尝试过的 fallback
- 每个 provider 的关键指标摘要
- 如果所有 provider 都是通过 fallback（非脚本）获取的，也照常汇报，不要省略
