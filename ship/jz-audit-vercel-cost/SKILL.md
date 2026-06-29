---
name: jz-audit-vercel-cost
version: "1.0.0"
description: "当需要读取、解释或反推 Vercel 账单、信用卡扣款、usage credit、effectiveCost、billedCost、Pro 固定费、Build Minutes 成本时使用。适用于核对 Vercel receipt/card charge、把 vercel usage 解析成准确应付金额、区分 Pro 平台费与 non-Pro 额外用量。"
---

# Vercel 账单核算

用于把 Vercel `usage` 数据解释成可和信用卡账单核对的数字。

## 核心口径

Vercel Pro 账单不要直接用 `effectiveCost` 当应付金额。

- `effectiveCost`：资源消耗参考，适合看 build/functions/image/edge 等资源用了多少。
- `billedCost`：Vercel CLI 对查询区间返回的最终计费字段，但里面可能含 `Pro` prorated 项。
- `Pro`：固定平台费，默认按 `$20` 单独处理。
- `non-Pro billed usage`：从 `services[].billedCost` 中排除 `name === "Pro"` 后求和。
- `projected receipt amount`：`Pro 固定费 + non-Pro billed usage`。

对信用卡或 receipt 核账时，优先使用：

```text
实际账单 ≈ pro_platform_fee + non_pro_billed_usage
```

不要使用：

```text
pro_platform_fee + total billedCost
```

也不要使用：

```text
effectiveCost
```

## Workflow

1. 确认 receipt date 或用户给出的扣款邮件日期。
   - 如果 receipt 显示每月 3 号，默认 billing cycle day 用 `3`。
   - 邮件日期和信用卡入账日期通常晚于 receipt date，不作为 usage range 边界。

2. 用脚本按 cycle 解析：

```bash
node ./audit-vercel-cost/scripts/parse-vercel-cost.mjs \
  --from 2026-02-03 \
  --to 2026-03-02 \
  --cycle-day 3 \
  --platform-fee 20
```

3. 对比用户账单：

```text
用户看到的扣款 - platform_fee
= 推定 non-Pro billed usage
```

4. 查异常成本时，先看 `topNonProBilledServices`，再看 `topEffectiveServices`。

## 输出解释

脚本输出 JSON：

- `effectiveUsageCostUsd`：资源消耗参考。
- `totalBilledCostUsd`：Vercel CLI 区间总 billedCost，可能含 Pro prorated 项。
- `proratedProBilledInUsageQueryUsd`：查询区间里 Vercel 返回的 Pro billedCost。
- `nonProBilledUsageUsd`：额外用量，核账时使用。
- `projectedReceiptAmountUsd`：`platform fee + non-Pro billed usage`。

## 注意

- `vercel usage --from/--to` 日期按洛杉矶时间解释。
- Vercel CLI 查询区间不一定等于 invoice period；以 receipt date 反推 cycle 边界。
- 如果 Vercel CLI 返回 `Costs not found (404)`，说明当前账号/CLI 对该历史区间不可查；不要把它记成 `$0`。
- 如果用户提供信用卡入账时间，标注为 `posting date`，不要当作 receipt date。
