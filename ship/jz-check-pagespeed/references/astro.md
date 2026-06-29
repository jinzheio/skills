---
framework: astro
version: "6"
updated: 2026-06-14
---

# Astro 性能优化参考

针对 Astro 6 + React islands 项目的已知优化模式。适用于任何使用 Astro 框架的站点。

## Island 水合策略

Astro 的 `client:*` 指令是控制 JS 加载的核心杠杆。

### 指令优先级（从轻到重）

| 指令 | 适用场景 | 成本 |
|------|---------|------|
| `client:load` | 几乎不用。需要立即交互的组件 | 最高 |
| `client:idle` | 低优先级组件（广告、tracker、非首屏 widget） | 低 |
| `client:visible` | 折叠线以下的内容 | 低 |
| `client:media` | 仅特定屏幕尺寸需要的组件 | 中 |
| `client:only` | 完全跳过服务端渲染（重型交互仅在前端渲染） | 高 |

### 模式：懒加载交互组件

```astro
---
// 差：所有组件立即水合
import HeavyWidget from '../components/HeavyWidget';
---
<HeavyWidget client:load />

---
// 好：根据使用场景选择水合策略
import HeavyWidget from '../components/HeavyWidget';
import AdBanner from '../components/AdBanner';
---
<HeavyWidget client:visible />  <!-- 用户滚动到才水合 -->
<AdBanner client:idle />       <!-- 空闲时才加载 -->
```

**检查清单：**
- `client:load` 是否仅有 0-1 个（理想状态）
- 广告是否使用 `client:idle` 或用户交互触发
- 首屏以下组件是否使用 `client:visible`

## React.lazy + Suspense

对于大型 React 组件，在 Astro 内配合 `client:only="react"` 使用 `React.lazy`：

```tsx
// 组件内懒加载重量级子组件
import { lazy, Suspense } from 'react';

const HeavyPanel = lazy(() => import('./HeavyPanel'));

export function PageInner() {
  return (
    <Suspense fallback={<div className="animate-pulse">Loading...</div>}>
      <HeavyPanel />
    </Suspense>
  );
}
```

## 图片优化

Astro 内置图片优化通过 `@astrojs/image`（v6 内置为 `<Image />` 和 `<Picture />`）：

```astro
---
import { Image } from 'astro:assets';
import heroImage from '../assets/hero.jpg';
---

<!-- 自动生成 srcset、webp/avif、width/height -->
<Image
  src={heroImage}
  alt="Hero"
  loading="lazy"
  decoding="async"
  widths={[400, 800, 1200]}
  sizes="(max-width: 800px) 100vw, 800px"
/>
```

**常见漏网之鱼（Lighthouse 报告的 "Improve image delivery"）：**
- 外部 CDN 图片缺少 `srcset` / sizes
- 未提供 WebP/AVIF 格式
- 首屏图片未加 `loading="eager"`（LCP 候选）
- `loading="lazy"` 但未设 `width/height`（布局偏移）

## View Transitions

Astro 6 内置 View Transitions，减少完整页面导航：

```astro
---
// src/layouts/BaseLayout.astro
import { ViewTransitions } from 'astro:transitions';
---
<html>
  <head>
    <ViewTransitions />
  </head>
  ...
</html>
```

## CSS 优化

- Tailwind — 使用 `@apply` 提取重复模式
- 内联关键 CSS — Astro 默认 scoped CSS 已自动 inline
- 未使用 CSS — Lighthouse 报告此项时检查动态导入的 CSS

## 字体优化

```astro
<!-- 预加载关键字体 -->
<link rel="preload" href="/fonts/inter-var.woff2" as="font" crossorigin />

<!-- 使用 font-display: swap 避免 FOIT -->
<style>
  @font-face {
    font-family: 'Inter';
    src: url('/fonts/inter-var.woff2') format('woff2');
    font-display: swap;
  }
</style>
```

## 第三方脚本

**常见模式：**

```ts
// 示例：用户交互触发懒加载（如广告脚本）
export function onLazyAdTrigger(callback: () => void) {
  const events = ['scroll', 'touchstart', 'keydown', 'mousemove'];
  const handler = () => {
    callback();
    events.forEach(e => document.removeEventListener(e, handler));
  };
  events.forEach(e => document.addEventListener(e, handler, { once: true }));
}
```

- 广告脚本延迟到用户首次交互后加载
- Umami tracker 使用 `client:idle`
- 清理函数移除注入的 `<script>` 元素

## 构建优化

```js
// astro.config.mjs
export default defineConfig({
  build: {
    inlineStylesheets: 'auto',  // 小 CSS 自动内联
  },
  vite: {
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-react': ['react', 'react-dom'],
          },
        },
      },
    },
  },
});
```

## 诊断映射

Lighthouse 审计 → Astro 修复：

| 审计 | 根因 | Astro 修复 |
|------|------|-----------|
| Reduce unused JavaScript | 大型 vendor bundle | `manualChunks` + `client:idle` |
| Render-blocking requests | 第三方脚本 | `onLazyAdTrigger` + `defer` |
| Time to Interactive | 太多 JS 水合 | 审查 `client:load` 实例 |
| Improve image delivery | 低效的 CDN 图片 | Astro `<Image />` + 格式 |
| Network dependency tree | 过多的链式请求 | 内联关键 CSS，预连接 |
| Minify CSS/JS | 未压缩 | Astro 构建默认已压缩 |
