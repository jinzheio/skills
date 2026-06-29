---
name: jz-check-pagespeed
version: "1.1.0"
description: "诊断页面速度性能。获取 PageSpeed Insights、CrUX 和 Cloudflare RUM Web Vitals 数据，给出改进建议。覆盖框架特定的优化模式。触发：页面慢不慢、PSI 分数、LCP/CLS/FCP 指标、优化建议。"
---

# 页面速度诊断

实时获取页面性能数据，分析瓶颈，给出可操作的改进方案。

## 数据源

三个源头，互补覆盖：

| 数据源 | 类型 | 提供者 | 需要什么 |
|--------|------|--------|---------|
| PageSpeed Insights | 实验室 + 现场（CrUX） | Google API | `PAGESPEED_API_KEY` |
| Cloudflare RUM | 真实用户（聚合） | Cloudflare GraphQL | `CLOUDFLARE_API_TOKEN`（通用 token，非 Analytics 专用 token） + Web Analytics 已启用 |

## 前置条件

- Python 3 + `requests`（内置 `urllib` 也可，脚本优先 `requests`）
- `PAGESPEED_API_KEY` — Google Cloud API key，启用 `pagespeedonline.googleapis.com`
- `CLOUDFLARE_API_TOKEN` — Cloudflare **通用** API token，需 `Account:Analytics:Read` 权限。**不要**用 Analytics-only token，权限不够
- Cloudflare Web Analytics 已在目标 zone 启用（Dashboard → Web Analytics → Add site）。这是 RUM 数据的前提，不是 API 能开的

## 输入

- 必填：`--url`，例如 `https://growagardencalculate.com`
- 可选：`--strategy` — `mobile`（默认）/ `desktop` / `both`
- 可选：`--fix` — 自动应用建议的修复（需要可编辑的 repo）

## 流程

### 1. PageSpeed Insights

端点：
```
GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed
  ?url=<url-encoded>
  &strategy=mobile|desktop
  &key=<PAGESPEED_API_KEY>
```

不要用 `pagespeedonline.googleapis.com/v5/pagespeedonline/...`——那会 404。域名是 `www.googleapis.com`。

认证方式：**API key**（URL 参数 `?key=`）。不是 ADC bearer token。

响应同时包含 Lighthouse 实验室数据（`lighthouseResult`）和 CrUX 现场数据（`loadingExperience`）。

### 2. Cloudflare RUM（真实用户指标）

#### 关键发现

- RUM 数据集在 **Account** 层级，不在 Zone：`AccountRumWebVitalsEventsAdaptiveGroups`、`AccountRumPerformanceEventsAdaptiveGroups`
- GraphQL endpoint 不变：`https://api.cloudflare.com/client/v4/graphql`
- 必须先调 `GET /accounts/{account_id}/rum/site_info/list` 拿到 `site_tag`
- GraphQL filter 中传 `siteTag`（不是 `zoneTag`）
- 需要通用 `CLOUDFLARE_API_TOKEN`（不是 Analytics-only token）——后者会在 GraphQL 返回 403

#### 获取 site_tag

```
GET https://api.cloudflare.com/client/v4/accounts/{account_id}/rum/site_info/list
Authorization: Bearer {CLOUDFLARE_API_TOKEN}
```

返回中 `ruleset.zone_name` 匹配 target hostname，取 `site_tag`。

#### Web Vitals 查询

```graphql
query WebVitals($accountTag: string, $filter: AccountRumWebVitalsEventsAdaptiveGroupsFilter_InputObject) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      rumWebVitalsEventsAdaptiveGroups(limit: 10, filter: $filter) {
        count
        avg { largestContentfulPaint firstContentfulPaint cumulativeLayoutShift timeToFirstByte }
        sum {
          lcpGood lcpNeedsImprovement lcpPoor lcpTotal
          fcpGood fcpNeedsImprovement fcpPoor fcpTotal
          clsGood clsNeedsImprovement clsPoor clsTotal
          ttfbGood ttfbNeedsImprovement ttfbPoor ttfbTotal
        }
        dimensions { date deviceType }
      }
    }
  }
}
```

变量：
```json
{
  "accountTag": "<ACCOUNT_ID>",
  "filter": {
    "datetime_geq": "2026-06-07T00:00:00Z",
    "datetime_lt": "2026-06-14T00:00:00Z",
    "siteTag": "<SITE_TAG>"
  }
}
```

#### 性能事件查询

```graphql
query Perf($accountTag: string, $filter: AccountRumPerformanceEventsAdaptiveGroupsFilter_InputObject) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      rumPerformanceEventsAdaptiveGroups(limit: 10, filter: $filter) {
        count
        avg { firstContentfulPaint firstPaint pageLoadTime }
        quantiles { firstContentfulPaintP50 firstContentfulPaintP75 firstContentfulPaintP95 }
        dimensions { date deviceType }
      }
    }
  }
}
```

## 凭据

加载顺序：
1. `~/.config/skills/jz-get-analytics/.env`（本机优先，已 `.gitignore`）
2. skill 根目录 `.env`（fallback）
3. `$CWD/.env`（项目 env，用于 Clarity 等项目级 token）

关键变量：
```
# PSI
PAGESPEED_API_KEY=...

# Cloudflare RUM — 必须用通用 token，不是 Analytics token
CLOUDFLARE_API_TOKEN=...
CLOUDFLARE_ANALYTICS_API_TOKEN=...  # 仅用于 zone-level 流量查询，权限不足以调 RUM
```

## 脚本

```bash
python3 .claude/skills/jz-check-pagespeed/scripts/check_pagespeed.py \
  --url https://growagardencalculate.com \
  --strategy both
```

## 阈值参考

| 指标 | 绿 (好) | 橙 (需改进) | 红 (差) |
|------|---------|------------|----------|
| Lighthouse Performance | ≥90 | 50–89 | <50 |
| FCP | ≤1.8s | ≤3.0s | >3.0s |
| LCP | ≤2.5s | ≤4.0s | >4.0s |
| TBT | ≤200ms | ≤600ms | >600ms |
| CLS | ≤0.1 | ≤0.25 | >0.25 |
| SI | ≤3.4s | ≤5.8s | >5.8s |
| TTI | ≤3.8s | ≤7.3s | >7.3s |

## 框架参考

- `references/astro.md` — Astro 6 + React islands 优化模式
- `references/tanstack-start.md` — TanStack Start SSR 优化模式

## 完成汇报

- PSI：Lab 总分 + 各 Web Vitals 颜色 + 诊断项（按严重度排序）
- CrUX：现场数据（如有）
- RUM：Web Vitals 好/需改进/差 百分比（含样本数）
- 框架特定建议
