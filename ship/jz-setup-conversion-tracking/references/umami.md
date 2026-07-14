# Umami 事件追踪参考

Umami 自定义事件 API 的使用方法和已投产验证的实现模式。

## API

Umami 提供 `window.umami.track(eventName, eventData?)`：

```ts
window.umami?.track('Signup Completed', {
  method: 'magic_link',
  time_to_complete_seconds: 42,
  locale: 'en',
});
```

- **eventName**：字符串，Proper Case，最大长度由各 Umami 实例决定
- **eventData**：可选，扁平的 `Record<string, unknown>`，value 用 string | number | boolean
- **返回值**：无

## 脚本加载时机

Umami script 通常是 `afterInteractive`（Next.js）或 `<script defer>`（静态站点）。意味着：

- 页面首次渲染时 `window.umami` 可能还不存在
- 用户快速点击时也可能不存在
- 需要 retry 机制，不能假设一次性调用成功

## Retry 工具函数

以下是已投产验证的实现。支持即时尝试 + 三档退避（300ms、1s、2.5s），每调用 `sent` flag 防重复。

```ts
export function trackUmami(
  eventName: string,
  eventData?: Record<string, unknown>,
) {
  if (typeof window === 'undefined') return;

  let sent = false;

  const tryTrack = () => {
    if (sent) return;
    if (!window.umami?.track) return;
    try {
      window.umami.track(eventName, eventData);
      sent = true;
    } catch {
      // Silently fail if Umami is not loaded
    }
  };

  // Attempt immediately
  tryTrack();

  // Retry on a backoff schedule
  setTimeout(tryTrack, 300);
  setTimeout(tryTrack, 1000);
  setTimeout(tryTrack, 2500);
}
```

## 跨页面漏斗状态管理

用 `sessionStorage` 存储漏斗起始状态。三个核心操作：标记起点、读取计算、防重复标记。

### 存储 key 约定

| Key | 存储内容 | 示例值 |
|---|---|---|
| `umami_signup_started_at` | 起始时间戳 (ms) | `1718000000000` |
| `umami_signup_method` | 注册方式 | `magic_link` / `google_oauth` |
| `umami_signup_completed` | 完成标记 | `1` |

```ts
const SIGNUP_STARTED_KEY = 'umami_signup_started_at';
const SIGNUP_METHOD_KEY = 'umami_signup_method';
const SIGNUP_COMPLETED_KEY = 'umami_signup_completed';

/** 标记注册流程开始 */
export function markSignupStarted(method?: string) {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(SIGNUP_STARTED_KEY, String(Date.now()));
    if (method) sessionStorage.setItem(SIGNUP_METHOD_KEY, method);
  } catch { /* ignore */ }
}

/** 获取注册耗时（秒），未开始时返回 null */
export function getSignupElapsedSeconds(): number | null {
  if (typeof window === 'undefined') return null;
  try {
    const started = sessionStorage.getItem(SIGNUP_STARTED_KEY);
    if (!started) return null;
    return Math.round((Date.now() - Number(started)) / 1000);
  } catch { return null; }
}

/** 获取注册方式 */
export function getSignupMethod(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return sessionStorage.getItem(SIGNUP_METHOD_KEY);
  } catch { return null; }
}

/** 检查是否已发送完成事件 */
export function hasTrackedSignupCompleted(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return sessionStorage.getItem(SIGNUP_COMPLETED_KEY) === '1';
  } catch { return false; }
}

/** 标记完成事件已发送 */
export function markSignupCompleted() {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(SIGNUP_COMPLETED_KEY, '1');
  } catch { /* ignore */ }
}
```

## 自建 Umami 管理 API

自建 Umami（如 `stats.jinzhe.io`）提供 admin API，用于创建 site、查询网站列表、创建 funnel 和 goal。需要 admin 账号的 username/password。

### 凭据

优先读取环境变量：

- `UMAMI_BASE_URL` — 如 `https://stats.jinzhe.io`（可以是 origin 或含 `/api`）
- `UMAMI_ADMIN_USERNAME` — admin 用户名
- `UMAMI_ADMIN_PASSWORD` — admin 密码

缺少任一变量时，回退到团队约定的 admin fallback 凭据。

Umami Cloud 或有明确 API-key auth 的兼容 provider 才用 `UMAMI_API_KEY` fallback。

### API Base 归一化

```bash
UMAMI_API_BASE="${UMAMI_BASE_URL%/}"
case "$UMAMI_API_BASE" in
  */api) ;;
  *) UMAMI_API_BASE="$UMAMI_API_BASE/api" ;;
esac
```

### Login Pattern

```bash
TOKEN=$(curl -sS "$UMAMI_API_BASE/auth/login" \
  -H "Content-Type: application/json" \
  --data "{\"username\":\"$UMAMI_ADMIN_USERNAME\",\"password\":\"$UMAMI_ADMIN_PASSWORD\"}" \
  | jq -r '.token')
```

### 常用 API

```bash
# 列出所有 website
curl -sS "$UMAMI_API_BASE/websites" \
  -H "Authorization: Bearer $TOKEN"

# 创建 website
curl -sS "$UMAMI_API_BASE/websites" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"name\":\"My Site\",\"domain\":\"example.com\"}"

# 获取 website 统计
curl -sS "$UMAMI_API_BASE/websites/<website-id>/stats" \
  -H "Authorization: Bearer $TOKEN" \
  --data "{\"startAt\":1717200000000,\"endAt\":1717800000000,\"unit\":\"day\"}"
```

## 前端注入

### Next.js App Router

Root layout 中注入 Umami script（`afterInteractive`）：

```tsx
// app/[locale]/layout.tsx
const umamiWebsiteId = process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID;
const umamiScript = process.env.NEXT_PUBLIC_UMAMI_SCRIPT
  ?? 'https://stats.jinzhe.io/script.js';

{umamiWebsiteId ? (
  <Script
    src={umamiScript}
    data-website-id={umamiWebsiteId}
    strategy="afterInteractive"
  />
) : null}
```

### Vite / 静态站点

在 `<head>` 中注入：

```html
<script defer
  src="https://stats.jinzhe.io/script.js"
  data-website-id="YOUR_WEBSITE_ID">
</script>
```

### 环境变量命名

不同框架用不同前缀，保持一致性：

| 框架 | 示例变量名 |
|---|---|
| Next.js | `NEXT_PUBLIC_UMAMI_WEBSITE_ID`、`NEXT_PUBLIC_UMAMI_SCRIPT` |
| Vite | `VITE_UMAMI_WEBSITE_ID`、`VITE_UMAMI_SCRIPT_URL` |
| Astro | `PUBLIC_UMAMI_WEBSITE_ID`、`PUBLIC_UMAMI_SCRIPT_URL` |

## 验证方法

1. 打开 DevTools → Network → 过滤 `script.js` 的 POST 请求
2. 触发目标行为
3. 观察 POST payload 中 `event_name` 和 `event_data`
4. 在 Umami Dashboard → Events 页面确认事件出现（延迟 1-2 分钟）

## 参考

- [Umami Custom Events 文档](https://docs.umami.is/docs/track-events)
- [Umami Tracker Functions](https://docs.umami.is/docs/tracker-functions)
- [Umami Funnel 配置](https://docs.umami.is/docs/funnel)
- [Umami Goals 配置](https://docs.umami.is/docs/goals)
