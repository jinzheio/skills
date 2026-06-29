# 归因追踪

把广告来源参数（UTM、gclid、fbclid 等）从 URL 带到结算 metadata，使付费可关联到广告渠道。

## 追踪的 URL 参数

所有主流广告平台的 click ID 和 UTM 参数：

```
gclid        — Google Ads click ID
gbraid       — Google Ads 增强归因 (iOS)
wbraid       — Google Ads 增强归因 (web)
gad_source   — Google Ads 来源标识
utm_source   — 流量来源
utm_medium   — 流量媒介
utm_campaign — 广告系列名
utm_term     — 关键词
utm_content  — 广告内容
fbclid       — Facebook/Instagram click ID
msclkid      — Microsoft Ads click ID
```

## 数据流

```
URL params → sessionStorage → checkout 构建 payload → Stripe metadata
```

### Step 1：着陆页存储

在首次 page view 时从 URL search params 提取并存储。

```ts
// 在 root page view tracker 中
const searchParams = useSearchParams();

useEffect(() => {
  if (!searchParams.toString()) return;
  storeAttributionFromSearchParams(searchParams);
}, [searchParams]);
```

### Step 2：存储合并逻辑

新访问合并已有存储（跨页面保留早期着陆信息），不覆盖首次着陆数据。

```ts
export function storeAttributionFromSearchParams(searchParams: URLSearchParams) {
  if (typeof window === 'undefined') return;

  const nextValue: Record<string, string> = {};
  for (const key of TRACKED_ATTRIBUTION_PARAMS) {
    const value = searchParams.get(key);
    if (value) nextValue[key] = value;
  }

  const current = readStoredAttribution();
  const merged = {
    ...current,
    ...nextValue,
    site: window.location.hostname,
    landing_path: current.landing_path || window.location.pathname,
    landing_url: current.landing_url || window.location.href,
    landing_referrer: current.landing_referrer || (document.referrer || ''),
  };

  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(merged));
}
```

### Step 3：Checkout 时构建 payload

结算时读出存储 + 当前浏览器上下文。

```ts
export function buildCheckoutAttributionPayload(extra?: {
  locale?: string;
  checkoutContext?: string;
  entryPoint?: string;
}) {
  const stored = readStoredAttribution();
  return {
    ...stored,
    site: window.location.hostname,
    checkout_path: window.location.pathname + window.location.search,
    checkout_url: window.location.href,
    referrer: document.referrer || '',
    ...(extra?.locale ? { locale: extra.locale } : {}),
    ...(extra?.checkoutContext ? { checkout_context: extra.checkoutContext } : {}),
    ...(extra?.entryPoint ? { entry_point: extra.entryPoint } : {}),
  };
}
```

### Step 4：Stripe metadata 写入

将归因 payload 转为 Stripe checkout session 的 metadata。

```ts
export function toStripeAttributionMetadata(
  input: Record<string, unknown> | null | undefined,
  fallbackSite = '',
) {
  const metadata: Record<string, string> = {};
  const allowedKeys = new Set([
    'site', 'landing_path', 'landing_url', 'landing_referrer',
    'checkout_path', 'checkout_url', 'referrer',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'gclid', 'gbraid', 'wbraid', 'gad_source', 'fbclid', 'msclkid',
    'locale', 'checkout_context', 'entry_point',
  ]);

  for (const [key, rawValue] of Object.entries(input ?? {})) {
    if (!allowedKeys.has(key)) continue;
    const value = String(rawValue ?? '').trim().slice(0, 500);
    if (!value) continue;
    metadata[key] = value;
  }

  if (!metadata.site && fallbackSite.trim()) {
    metadata.site = fallbackSite.trim().slice(0, 500);
  }

  return metadata;
}
```

服务端 checkout route 中使用：

```ts
// app/api/billing/checkout/route.ts
const attributionMeta = toStripeAttributionMetadata(
  metadata ?? {},
  'clawsimple.com',
);

const session = await stripe.checkout.sessions.create({
  // ...
  metadata: {
    userId,
    ...attributionMeta,
  },
  subscription_data: {
    metadata: {
      ...attributionMeta,
    },
  },
});
```

### 读取 Stripe metadata

在 `stripe checkout.session.completed` webhook 或 dashboard 中查看。

## 存储 key

使用项目前缀避免冲突：`<project>.ads.attribution`

## 重要约束

- 所有 value 截断到 500 字符（Stripe metadata 限制）
- 不允许保存 IP、user agent、device fingerprint 等 PII
- 只记录广告 channel，不记录个人标识符
