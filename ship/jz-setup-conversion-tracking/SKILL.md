---
name: jz-setup-conversion-tracking
description: "为网站或 Web 应用实现转化漏斗事件追踪。触发语包括 track conversion、加埋点、转化追踪、漏斗事件、event tracking、埋点方案、add analytics events、conversion funnel、track signup、track checkout。不是用于接入 Umami 脚本本身（用 jz-setup-site-analytics），也不是用于读取已有统计数据（用 site-metrics）。"
---

# 转化事件追踪

为 Web 应用设计和实现转化漏斗事件。不负责接入统计脚本本身，只负责埋点：设计事件体系、实现发送代码、确保事件可靠触发。

## 前置条件

- 页面已有 Umami 脚本（或类似 analytics）注入
- 项目能正常运行，可以测试事件是否触发
- 如果是 Next.js App Router，有一致的 `'use client'` 用法约定

缺少统计脚本时，先 `jz-setup-site-analytics`。

## 输入

- 现有转化路径：用户在哪些页面做什么操作
- 目标事件列表：用户明确要求的事件，或从转化路径推导
- 项目前端框架（Next.js / Vite / 静态站点 等）

## 目标

- 完成事件命名设计，所有事件名和属性名一致
- 实现前端发送工具函数
- 在目标组件中埋入事件调用
- 用 dev tools 或 Umami 管理后台确认事件到达

## 事件命名规范

**事件名：Proper Case，Object-Action**。读起来像自然语言。

- ✅ `Signup Completed`
- ✅ `Deployment Started`
- ✅ `Checkout Started`
- ❌ `signup_completed` / `signupCompleted`

**属性名：snake_case**。与 Umami 内部字段风格一致。

- ✅ `{ plan_id, time_to_complete_seconds, cta_location }`
- ❌ `{ planId, timeToCompleteSeconds }`

**CTA 点击**统一用 `CTA Clicked`，用 `cta_location` property 区分位置：`hero` / `pricing_card` / `pricing_bottom` / `blog` / `nav` / `footer`。

## 事件体系设计

标准 SaaS 转化漏斗最少需要这些事件：

| 漏斗阶段 | 事件名 | 关键属性 |
|---|---|---|
| 到达 | `Landing Page Viewed` | `locale`, `path` |
| 兴趣 | `Pricing Page Viewed` | `locale` |
| 行动 | `CTA Clicked` | `cta_location`, `locale` |
| 注册开始 | `Signup Started` | `method`, `source_page` |
| 注册完成 | `Signup Completed` | `method`, `time_to_complete_seconds` |
| 激活开始 | `Setup Wizard Started` | `entry_point` |
| 激活完成 | `First Deployment Started` | `provider`, `region` |
| 价值 | `First Deployment Completed` | `provider`, `region`, `duration_seconds` |
| 付费 | `Checkout Started` | `plan_id`, `currency` |
| 付费确认 | `Payment Success` | `plan_id`, `amount`, `subscription_id` |
| 流失 | `Subscription Cancelled` | `plan_id`, `reason`, `lifetime_days` |

不需要一次实现全部。按当前产品的转化路径挑对应的实现。

## 实现模式

以下模式来自已投产验证的实现。具体发送实现读取对应 analytics 工具的 reference 文件。

### 模式 A：页面/区块曝光

页面加载或滚动到某区块时发送一次。用 `useEffect` 或 `IntersectionObserver`。

```tsx
// Page mount
useEffect(() => {
  trackUmami('Landing Page Viewed', {
    locale,
    path: window.location.pathname,
  });
}, [locale]);

// Scroll into view (track once)
useEffect(() => {
  const el = ref.current;
  if (!el) return;
  let fired = false;
  const obs = new IntersectionObserver(([entry]) => {
    if (entry?.isIntersecting && !fired) {
      fired = true;
      trackUmami('Pricing Page Viewed', { locale });
    }
  }, { threshold: 0.3 });
  obs.observe(el);
  return () => obs.disconnect();
}, [locale]);
```

### 模式 B：点击事件

直接在 `onClick` 中发送。

```tsx
<button
  onClick={() => {
    trackUmami('CTA Clicked', { cta_location: 'hero', locale });
    markSignupStarted('magic_link');
  }}
>
  Get Started
</button>
```

### 模式 C：跨页面漏斗状态

用 `sessionStorage` 存储漏斗起点状态，在后续页面读取并计算完成时间。

**适用场景**：Signup Started → Signup Completed、Checkout Started → Payment Success 等跨页面事件。

**实现步骤**：

1. 起点页面：存储时间戳和关键参数到 `sessionStorage`
2. 终点页面：读取时间戳、计算耗时、发送事件、标记已发送

```tsx
// Step 1: 起点 — 存储
export function markSignupStarted(method?: string) {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem('umami_signup_started_at', String(Date.now()));
    if (method) sessionStorage.setItem('umami_signup_method', method);
  } catch { /* ignore */ }
}

// Step 2: 终点 — 读取、计算、发送
export function getSignupElapsedSeconds(): number | null {
  if (typeof window === 'undefined') return null;
  try {
    const started = sessionStorage.getItem('umami_signup_started_at');
    if (!started) return null;
    return Math.round((Date.now() - Number(started)) / 1000);
  } catch { return null; }
}

// 组件中
useEffect(() => {
  if (!session?.data?.session) return;
  if (hasTrackedSignupCompleted()) return;
  const elapsed = getSignupElapsedSeconds();
  if (elapsed === null) return; // 没有起点记录，不发送
  const method = getSignupMethod();
  trackUmami('Signup Completed', { method, time_to_complete_seconds: elapsed, locale });
  markSignupCompleted();
}, [session, locale]);
```

**防重复**：用 sessionStorage 标记 `completed`，避免每次组件 mount 都重新发送。

### 模式 D：Wizard 单次追踪

用户与某个表单或流程交互时，只追踪第一次。

```tsx
const interactedRef = useRef(false);

const handleFocus = () => {
  if (interactedRef.current) return;
  interactedRef.current = true;
  trackUmami('Setup Wizard Started', { entry_point: 'homepage' });
};
```

### 模式 E：Google Ads 转化

需要同时发 Umami 事件和 Google 转化事件时，两边独立发送。

```tsx
// Umami — 漏斗分析
trackUmami('Checkout Started', { plan_id, currency });

// Google Ads — 转化追踪
trackGoogleEvent('begin_checkout', { ...attributionPayload });
trackGoogleAdsConversion({
  sendTo: process.env.NEXT_PUBLIC_GOOGLE_ADS_CONVERSION_BEGIN_CHECKOUT,
  value,
  currency: 'USD',
});
```

### 模式 F：归因数据附带

结算或关键转化事件附带归因信息（UTM、gclid、fbclid 等），让 Stripe metadata 可关联到广告来源。

核心思路：URL 参数 → sessionStorage → checkout 时读出 → 作为 Stripe metadata 提交。

详细实现参考 `references/attribution.md`。

## 前端注入点

### Next.js App Router

- **Analytics script**：在 root `layout.tsx` 用 `<Script strategy="afterInteractive">` 注入 Umami、GTM、Clarity
- **页面事件**：在具体 `page.tsx` 中 mount `<PageViewTracker>` 组件
- **组件事件**：在交互组件内部直接调用

### CSP 配置

如果项目有 CSP header，需要 whitelist analytics 域名。在 `next.config.ts` 的 CSP 配置中添加：

- **script-src**: stats 域名、googletagmanager、clarity
- **img-src**: stats 域名、google 相关域名
- **connect-src**: stats 域名、google-analytics 域名

## 验证

实现后必须确认事件到达：

1. 打开浏览器 DevTools → Network 标签 → 过滤 `stats` 或 analytics 域名
2. 触发目标行为
3. 确认 POST 请求已发送，payload 包含预期事件名和属性
4. 在 Umami dashboard 的 Events 页面确认事件出现（可能有 1-2 分钟延迟）

## 常见错误

- **事件不触发**：Umami script 是 `afterInteractive`，可能在组件渲染时还未加载。用 retry 机制处理，参考对应 analytics 工具的 reference。
- **重复事件**：`useEffect` 依赖数组写错，或没有 `satisfies` guard。跨页面事件必须用 sessionStorage 防重复。
- **属性格式不一致**：同一个概念用了不同 key（`planId` vs `plan_id`）。命名阶段订好规范并统一检查。
- **缺少归因**：checkout 事件没有附带 UTM/广告参数，导致无法追踪付费来源。确保关键转化事件总是调用 `buildCheckoutAttributionPayload`。

## 完成汇报

按事件列出：

- `done` — 已实现并验证
- `blocked` — 缺少前置条件（说明缺什么）
- `pending` — 已实现但未验证（说明如何验证）

每项说明文件位置和关键代码片段。
