---
framework: tanstack-start
version: "1"
updated: 2026-06-14
---

# TanStack Start 性能优化参考

针对 TanStack Start + React + Cloudflare Workers 项目的已知优化模式。

## SSR 吞吐优化

TanStack Start 的 SSR 性能优化核心原则：

1. **SSR 跳过响应式系统** — 服务端只渲染一次，无需订阅 Store。使用构建时常量 `isServer` 分支：
   ```typescript
   if (isServer) return snapshot       // 无需 store 订阅
   return useStore(router, { ... })    // 客户端正常行为
   ```
   `isServer` 是 Vite/esbuild 构建时常量，死代码消除后只有一个分支存在。

2. **避免热路径中的 `new URL()`** — URL 解析在高吞吐量时成本显著。先用廉价路径检查，只在必要时解析：
   ```typescript
   // 先检查，只在需要时解析
   if (isSafeInternal(to)) { /* fast path */ }
   else { const url = new URL(to, base); /* external handling */ }
   ```

3. **避免热路径中的 `delete`** — 对象形状改变触发 V8 HiddenClass 去优化。改用赋值 `= undefined`。

## Streaming SSR

TanStack Start 默认支持 streaming。使用 `defaultStreamHandler` 渐进式发送 HTML：

```typescript
import { createStartHandler, defaultStreamHandler } from '@tanstack/react-start/server'

const handler = createStartHandler({
  handler: defaultStreamHandler,
})
```

**Skeleton 模式** — `pendingComponent` + `pendingMs`：

```typescript
export const Route = createFileRoute('/articles')({
  loader: async () => {
    const [posts, categories] = await Promise.all([getPosts(), getCategories()])
    return { posts, categories }
  },
  pendingComponent: () => <PostGridSkeleton />,  // 流式先发骨架
  pendingMs: 100,      // <100ms 不显示骨架（太快）
  pendingMinMs: 200,   // 骨架最少显示 200ms（避免闪烁）
})
```

## Route Preloading

### Link 级预取

路由级启用预取，悬停时自动预加载：

```typescript
export const Route = createFileRoute('/products')({
  preload: true,  // 悬停/聚焦时预加载路由 chunks + loader 数据
  loader: async () => ({ products: await getProducts() }),
})
```

Router 自动在 hover/touch/focus 时触发预加载，导航感知瞬时完成。

### `beforeLoad` 中提前加载数据

```typescript
export const Route = createFileRoute('/dashboard')({
  beforeLoad: async ({ context }) => {
    await Promise.all([
      context.queryClient.ensureQueryData(userQueryOptions),
      context.queryClient.ensureQueryData(dashboardStatsQueryOptions),
    ])
  },
})
```

数据在渲染前保证存在于缓存，组件中直接 `useSuspenseQuery`。

## TanStack Query 最佳实践

### queryOptions 单一数据源

```typescript
// queryOptions 作为 queryKey + queryFn 的唯一定义
export const userQueryOptions = queryOptions({
  queryKey: ['user', userId],
  queryFn: () => fetchUser(userId),
  staleTime: 60_000,
})

// 在 beforeLoad（预取）、组件（useSuspenseQuery）、mutation（invalidate）中复用
```

### SSR 脱水/水合

```typescript
import { setupRouterSsrQueryIntegration } from '@tanstack/react-router-ssr-query'
// 自动将服务端 query 状态脱水 → 客户端水合
```

### 状态分离

| 数据类型 | 存储 |
|---------|------|
| 服务端数据（API 响应、用户信息） | TanStack Query |
| 客户端状态（弹窗、侧栏） | TanStack Store / React state |

不要将服务端数据复制到本地状态——让 Query 管理缓存、过时和失效。

## CDN Asset 部署

### `transformAssets` — CDN 重写

```typescript
const handler = createStartHandler({
  handler: defaultStreamHandler,
  transformAssets: {
    transform: ({ kind, url }) => ({
      href: `https://cdn.example.com${url}`,
      crossOrigin: 'anonymous',
    }),
    cache: true,    // 生产构建时计算一次
    warmup: true,   // 服务启动时预热
  },
})
```

### Vite `base` 配置

| `base` | SSR assets | 客户端导航 chunks |
|:---|:---|:---|
| `'/'` (默认) | CDN 通过 `transformAssets` | App 服务器 ❌ |
| `''` | CDN 通过 `transformAssets` | CDN ✅ |

使用 `base: ''` 让客户端导航的代码分割 chunks 也从 CDN 加载。

## 多级缓存

```
Edge Cache (Cloudflare, 最近 PoP)
  → KV (持久化，跨区域)
    → TanStack Query 缓存 (浏览器内存)
```

每层使用 stale-while-revalidate 策略。

## 部署

### Cloudflare Workers

`@tanstack/react-start` 原生支持 Cloudflare Workers adapter。Watt 可在多核服务器上提供更好的 SSE 尾延迟（p99 改善 ~9%）。

```typescript
// app.config.ts
export default defineConfig({
  server: {
    preset: 'cloudflare-pages',
  },
})
```

## 诊断映射

Lighthouse 审计 → TanStack Start 修复：

| 审计 | 根因 | 修复 |
|------|------|------|
| Reduce unused JavaScript | SSR 仍有大 chunk | `manualChunks` + route-based splitting |
| Render-blocking requests | 未预加载关键资源 | `beforeLoad` + `ensureQueryData` |
| Time to Interactive | 客户端 hydration 过重 | streaming + `pendingComponent` |
| Network dependency tree | 链式 data fetching | `Promise.all` 并行化 |
| Avoid large layout shifts | 无骨架屏 | `pendingComponent` 骨架 |
| Serve static assets with CDN | 无 CDN 配置 | `transformAssets` + Vite `base: ''` |
