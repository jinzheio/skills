# Astro 测试参考

## 依赖

```json
{
  "devDependencies": {
    "vitest": "^4",
    "@testing-library/jest-dom": "^6",
    "happy-dom": "^20",
    "@vitest/coverage-v8": "^4",
    "@astrojs/test-utils": "latest"
  }
}
```

如果使用 React/Preact/Svelte 组件，额外装对应的 Testing Library。

## vitest.config.ts 模板

```typescript
import { getViteConfig } from "astro/config";

export default getViteConfig({
  test: {
    include: ["src/**/*.{test,spec}.{ts,tsx,js,jsx}"],
    environment: "happy-dom",
    setupFiles: ["./src/test-setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary"],
      include: ["src/**/*.{ts,tsx,js,jsx}"],
      exclude: [
        "src/**/*.test.*",
        "src/**/*.spec.*",
        "src/env.d.ts",
      ],
    },
  },
});
```

## 测试策略

### 内容集合（Content Collections）

```typescript
import { describe, expect, it } from "vitest";
import { getCollection } from "astro:content";

// 验证所有博客文章都有必填字段
describe("blog collection", () => {
  it("all posts have required frontmatter", async () => {
    const posts = await getCollection("blog");
    for (const post of posts) {
      expect(post.data.title).toBeTruthy();
      expect(post.data.publishDate).toBeInstanceOf(Date);
    }
  });
});
```

### 辅助函数

提取工具函数单独测试：

```typescript
// src/lib/format-date.ts
export function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

// src/lib/format-date.test.ts
import { describe, expect, it } from "vitest";
import { formatDate } from "./format-date";

it("formats date to YYYY-MM-DD", () => {
  expect(formatDate(new Date("2026-06-15"))).toBe("2026-06-15");
});
```

### 组件测试（Astro 组件）

Astro 组件（`.astro` 文件）的测试需要渲染到 HTML 字符串：

```typescript
import { describe, expect, it } from "vitest";
import { experimental_AstroContainer as AstroContainer } from "astro/container";

describe("Card.astro", () => {
  it("renders with title", async () => {
    const container = await AstroContainer.create();
    const result = await container.renderToString(
      await import("./Card.astro"),
      { props: { title: "Hello" } }
    );
    expect(result).toContain("<h2>Hello</h2>");
  });
});
```

### E2E 测试

Astro 项目通常用 Playwright：

```bash
pnpm playwright install
```

```typescript
// playwright.config.ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  webServer: {
    command: "pnpm preview --port 4321",
    url: "http://localhost:4321",
    reuseExistingServer: !process.env.CI,
  },
  use: { baseURL: "http://localhost:4321" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
```

## CI 模板

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: 'pnpm'
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm exec astro check
      - run: pnpm test:ci
      - run: pnpm test:coverage
      - run: pnpm build
```

## Astro 特殊考虑

- **`.astro` 组件**：不能像 React 组件那样用 Testing Library。用 `AstroContainer` 渲染或提取纯逻辑函数测
- **SSR/SSG 混合**：`astro check` 做类型验证比 `tsc` 更好（它能检查 `.astro` 文件）
- **岛屿架构**：框架组件（React/Svelte）用各自的测试库，Astro 胶水层单独测
- **内容集合**：`getCollection()` 在测试中可直接用，验证 schema
- **无路由测试**：Astro 是文件路由，不需要测路由配置
