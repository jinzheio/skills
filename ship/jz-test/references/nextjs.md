# Next.js 测试参考

## 依赖

```json
{
  "devDependencies": {
    "vitest": "^4",
    "@testing-library/react": "^16",
    "@testing-library/jest-dom": "^6",
    "@testing-library/user-event": "^14",
    "happy-dom": "^20",
    "@vitest/coverage-v8": "^4"
  }
}
```

## vitest.config.ts 模板

```typescript
import path from "path";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: [...configDefaults.exclude, ".claude/worktrees/**"],
    environment: "happy-dom",
    setupFiles: ["./src/test-setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary"],
      reportsDirectory: "./coverage",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.ts",
        "src/**/*.spec.ts",
        "src/**/__mocks__/**",
        "src/test-setup.ts",
        "src/**/*.d.ts",
      ],
      thresholds: {
        lines: 0, // 设 0 先建立基线
        branches: 0,
        functions: 0,
        statements: 0,
      },
    },
  },
});
```

第一次跑后根据实际覆盖率调整 thresholds。

## test-setup.ts

```typescript
import "@testing-library/jest-dom/vitest";
```

## package.json scripts

```json
{
  "test": "vitest run",
  "test:ci": "vitest run",
  "test:watch": "vitest",
  "test:coverage": "vitest run --coverage",
  "test:e2e": "playwright test -c scripts/e2e/playwright.config.ts"
}
```

## 测试模式

### API Route 测试

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "./route";

// Mock 外部依赖用 vi.hoisted() + vi.mock()
const mockGetSession = vi.hoisted(() => vi.fn());

vi.mock("@/lib/auth/session", () => ({
  getRequestSession: mockGetSession,
}));

function buildRequest(body?: unknown, method = "POST"): NextRequest {
  const url = "http://localhost:3000/api/test";
  return new NextRequest(url, {
    method,
    headers: { "content-type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

// 测试 auth 守卫
it("returns 401 when no session", async () => {
  mockGetSession.mockResolvedValue(null);
  const res = await POST(buildRequest({}));
  expect(res.status).toBe(401);
});
```

### 纯逻辑测试

不需要 `happy-dom` 环境，不需要 mock：

```typescript
import { describe, expect, it } from "vitest";

describe("helperFunction", () => {
  it("handles edge case: empty input", () => {});
  it("handles edge case: null input", () => {});
  it("handles edge case: extreme values", () => {});
});
```

### DB mock 测试

```typescript
import { vi } from "vitest";

const mockDbQuery = vi.hoisted(() => vi.fn());

vi.mock("@/lib/db", () => ({
  db: {
    select: vi.fn(() => ({
      from: vi.fn(() => ({
        where: vi.fn(() => ({
          orderBy: vi.fn(() => ({
            limit: vi.fn(() => mockDbQuery()),
          })),
        })),
      })),
    })),
  },
}));
```

### 组件测试

```typescript
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MyComponent } from "./my-component";

it("renders and handles click", async () => {
  const user = userEvent.setup();
  render(<MyComponent />);
  await user.click(screen.getByRole("button"));
  expect(screen.getByText("Clicked")).toBeInTheDocument();
});
```

## Playwright E2E 配置

```typescript
import { defineConfig, devices } from '@playwright/test';
import path from 'path';

const rootDir = path.resolve(__dirname, '../..');

export default defineConfig({
  testDir: __dirname,
  testMatch: '*.spec.ts',
  fullyParallel: false,
  workers: 1,
  reporter: 'html',
  webServer: {
    command: 'pnpm dev --port 3000',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
    cwd: rootDir,
  },
  use: {
    baseURL: process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
```

## CI 模板 (.github/workflows/ci.yml)

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
      - run: pnpm exec tsc --noEmit
      - run: pnpm test:ci
      - run: pnpm test:coverage
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: coverage-report
          path: coverage/
          retention-days: 7
      - run: pnpm build
```

## Next.js 特殊考虑

- **Server Components**：要在 Node 环境中测试，不能用 `happy-dom`。用纯逻辑测试提取的 helper 函数
- **`next/headers`**：API route 之外不能直接 mock `headers()` / `cookies()`。提取纯函数单独测
- **Edge Runtime**：少用或避免，Vitest 天然支持 nodejs runtime 的 API routes
- **Middleware**：用 `NextRequest` + `NextResponse` 测试，参考 API route 模式
