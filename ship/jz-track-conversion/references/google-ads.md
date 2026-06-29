# Google Ads / Google Analytics 事件参考

通过 gtag 发送 Google Analytics 事件和 Google Ads 转化的实现模式。

## 前提

项目已注入 Google Tag Manager / gtag script。使用 `NEXT_PUBLIC_GOOGLE_TAG_ID` 或 `NEXT_PUBLIC_GOOGLE_ADS_ID` 环境变量。

## gtag 脚本注入

### Next.js App Router

```tsx
const GOOGLE_TAG_ID = (process.env.NEXT_PUBLIC_GOOGLE_TAG_ID ?? '').trim();
const GOOGLE_ADS_ID = (process.env.NEXT_PUBLIC_GOOGLE_ADS_ID ?? '').trim();

if (!GOOGLE_TAG_ID) return null;  // 没配置就不注入

const accountIds = Array.from(new Set([GOOGLE_TAG_ID, GOOGLE_ADS_ID].filter(Boolean)));

return (
  <>
    <Script
      src={`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GOOGLE_TAG_ID)}`}
      strategy="afterInteractive"
    />
    <Script id="google-ads-tag" strategy="afterInteractive">
      {`
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        window.gtag = window.gtag || gtag;
        gtag('js', new Date());
        ${accountIds.map((id) => `gtag('config', '${id}', { send_page_view: false });`).join('\n')}
      `}
    </Script>
  </>
);
```

注意 `send_page_view: false`。Page view 通过 `<PageViewTracker>` 组件手动发送，以便附带归因数据。

## GA4 事件

```ts
export function trackGoogleEvent(eventName: string, params: Record<string, unknown> = {}) {
  if (typeof window === 'undefined' || typeof window.gtag !== 'function') return false;
  window.gtag('event', eventName, {
    ...readStoredAttribution(),  // 自动附带归因参数
    ...params,
  });
  return true;
}
```

常用事件名（GA4 标准）：

- `page_view`
- `begin_checkout`
- `purchase`
- `sign_up`
- `login`
- `generate_lead`

## Google Ads 转化事件

```ts
type GoogleAdsConversionOptions = {
  sendTo?: string | null;       // AW-XXXXXXX/XXXXXXX
  value?: number;
  currency?: string;
  transactionId?: string;
  eventCallback?: () => void;
  eventTimeoutMs?: number;      // 默认 1200ms
  extraParams?: Record<string, unknown>;
};

export function trackGoogleAdsConversion({
  sendTo,
  value,
  currency,
  transactionId,
  eventCallback,
  eventTimeoutMs = 1200,
  extraParams,
}: GoogleAdsConversionOptions) {
  if (!sendTo) {
    eventCallback?.();
    return false;
  }

  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    eventCallback?.();
  };

  const sent = trackGoogleEvent('conversion', {
    send_to: sendTo,
    value,
    currency,
    transaction_id: transactionId,
    event_callback: finish,
    ...extraParams,
  });

  if (!sent) {
    finish();
    return false;
  }

  // 安全超时：确保 callback 一定会被调用
  window.setTimeout(finish, eventTimeoutMs);
  return true;
}
```

## 环境变量

| 变量 | 用途 | 格式 |
|---|---|---|
| `NEXT_PUBLIC_GOOGLE_TAG_ID` | GA4 Measurement ID | `G-XXXXXXXXXX` |
| `NEXT_PUBLIC_GOOGLE_ADS_ID` | Google Ads account ID | `AW-XXXXXXXXX` |
| `NEXT_PUBLIC_GOOGLE_ADS_CONVERSION_*` | 各转化动作的 conversion ID + label | `AW-XXXXXXXXX/XXXXXXXXX` |

GTAG_ID 和 ADS_ID 可相同也可不同。如果 ADS_ID 缺失则只设 GTAG_ID。

转化 label 名称建议与业务事件对应：

- `NEXT_PUBLIC_GOOGLE_ADS_CONVERSION_BEGIN_CHECKOUT`
- `NEXT_PUBLIC_GOOGLE_ADS_CONVERSION_DEPLOY_STARTED`
- `NEXT_PUBLIC_GOOGLE_ADS_CONVERSION_DEPLOY_COMPLETED`

## 使用

### 单发 GA 事件

```ts
trackGoogleEvent('begin_checkout', {
  currency: 'USD',
  value: 14.99,
  items: [{ item_name: 'seat-standard', quantity: 1 }],
});
```

### 同时发 GA 事件和 Google Ads 转化

```ts
// GA event — 用于分析
trackGoogleEvent('deploy_started', {
  deployment_sid,
  seat_plan: 'seat-standard',
});

// Google Ads conversion — 用于广告优化
trackGoogleAdsConversion({
  sendTo: process.env.NEXT_PUBLIC_GOOGLE_ADS_CONVERSION_DEPLOY_STARTED,
  value: 14.99,
  currency: 'USD',
  extraParams: { deployment_sid, seat_plan },
});
```

## 注意事项

- `trackGoogleAdsConversion` 的 `eventCallback` 用于导航跳转场景（如点击后 redirect 到 Stripe）。发送转化后才跳转，避免转化记录丢失
- `eventTimeoutMs` 是兜底超时——gtag 回调未触发时强制继续
- 所有事件自动附带 `readStoredAttribution()` 返回的归因参数
