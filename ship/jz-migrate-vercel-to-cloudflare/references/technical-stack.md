# 技术栈推荐

在框架、SSR、i18n、Pages、Workers、OpenNext 之间做取舍时读取。普通域名交接或单一路径部署不必读取。

## 判断顺序

1. 识别现状：框架、路由、渲染方式、API、认证、数据源、i18n、Vercel 平台绑定、部署命令、产物目录。
2. 判断最少改动迁移：保留当前框架和功能，把 Vercel 平台能力替换成 Cloudflare 能力。
3. 判断是否值得重选技术栈：在用户接受删减或重构时，选择更简单的 Cloudflare 原生路径。
4. 输出推荐方案和备选方案，说明哪些用户约束会改变推荐。
5. 向用户确认关键约束。不要替用户假设必须保留 Next.js、i18n、SSR 或多语言。

联网可用时，先查 Cloudflare 官方文档当前口径。优先参考：

- Workers Next.js guide：完整 Next.js 应用用 OpenNext adapter 部署到 Workers。
- Pages Next.js guide：完整 SSR Next.js 应用参考 Workers guide；静态 Next.js 站点可走 Pages 静态方案。
- Workers Astro guide：Astro 可部署到 Workers；纯静态 Astro 只需要静态产物；SSR 才添加 `@astrojs/cloudflare`。
- Workers static assets / full-stack framework guides：SSR 或 request-time 数据获取属于 full-stack Worker 应用，静态资产可直接由 Cloudflare 承载。

## 推荐口径

- 纯内容站、博客、文档、个人项目展示、作品集、营销页，页面可在构建期生成，且用户接受删减 SSR/i18n 或换框架：推荐 Astro + Cloudflare Pages 或 Workers Static Assets。
- 已经是 Astro 且纯静态：推荐继续 Astro 静态输出；不要为了静态站添加 `@astrojs/cloudflare`。
- Astro 需要 SSR、session、Cloudflare bindings 或 request-time 数据：推荐 Astro + `@astrojs/cloudflare` + Workers。
- 需要保留 Next.js App Router/Pages Router、SSR、ISR、Middleware、Route Handlers、API routes、Server Actions、动态图片优化、复杂 i18n 或低改动迁移：推荐 Next.js + OpenNext for Cloudflare + Workers。
- 静态 Next.js，没有 SSR、Middleware、API、Server Actions、动态路由运行时依赖：可静态导出后部署到 Pages 或 Workers Static Assets，但要检查 `next/image`、动态路由、metadata、sitemap 和重定向。
- 大量 Vercel 平台服务：先列替代关系，例如 Blob 到 R2、Postgres 到 D1/Hyperdrive/外部数据库、KV 到 Workers KV、Cron 到 Workers Cron Triggers、Analytics 到 Cloudflare Web Analytics 或其他方案。

## 输出格式

```text
推荐方案：<方案名>
原因：<根据项目类型、约束和 Cloudflare 官方口径说明>
改动量：<低/中/高，说明主要改动>
风险：<部署、功能、SEO、数据或运维风险>

备选方案：<方案名>
适用条件：<什么时候选它>
取舍：<它比推荐方案多/少什么>

我需要确认这些约束：
- <问题 1>
- <问题 2>
- <问题 3>
```

## 示例

- 纯内容站或个人项目展示，当前用 Next.js 只是为了页面组织，没有 API、SSR、Middleware、Server Actions；用户接受只保留英文并移除 i18n：推荐 Astro + Cloudflare Pages，备选 Next.js + OpenNext/Workers。
- Next.js 站点使用 middleware 做 locale 跳转、保留中英文路由、依赖 SSR 或 Route Handlers：推荐 Next.js + OpenNext/Workers，备选重构到 Astro。
- Astro 内容站纯静态：推荐 Astro 静态输出 + Pages 或 Workers Static Assets，备选 Astro + Cloudflare adapter 只适合需要 SSR 或 bindings 的情况。
