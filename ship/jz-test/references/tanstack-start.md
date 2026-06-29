# TanStack Start 测试参考

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
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    environment: "happy-dom",
    setupFiles: ["./src/test-setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.*",
        "src/**/*.spec.*",
        "src/test-setup.ts",
        "src/routeTree.gen.ts",
        "src/**/*.d.ts",
      ],
    },
  },
});
```

TanStack Start 生成的 `routeTree.gen.ts` 必须在 coverage exclude 中。

## test-setup.ts

```typescript
import "@testing-library/jest-dom/vitest";
```

## 测试策略

### Server Functions（API 层）

TanStack Start 的 server functions 类似 Next.js API routes：

```typescript
import { describe, expect, it, vi } from "vitest";

// Mock 数据库
const mockDb = vi.hoisted(() => ({
  query: vi.fn(),
}));

vi.mock("@/lib/db", () => ({ db: mockDb }));

describe("createUser server function", () => {
  it("validates email format", async () => {
    // 测试 server function 中的验证逻辑
  });

  it("handles duplicate email error", async () => {
    mockDb.query.mockRejectedValue(new Error("duplicate key"));
    // 测试错误处理
  });
});
```

### 路由组件测试

```typescript
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HomeRoute from "./routes/index";

describe("Home route", () => {
  it("renders the hero section", () => {
    render(<HomeRoute />);
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("handles form submission", async () => {
    const user = userEvent.setup();
    render(<HomeRoute />);
    await user.click(screen.getByRole("button", { name: /submit/i }));
    // 验证提交后的状态
  });
});
```

### 纯逻辑函数

```typescript
import { describe, expect, it } from "vitest";

function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

describe("validateEmail", () => {
  it("accepts valid emails", () => {
    expect(validateEmail("a@b.com")).toBe(true);
  });
  it("rejects missing @", () => {
    expect(validateEmail("notanemail")).toBe(false);
  });
  it("rejects empty string", () => {
    expect(validateEmail("")).toBe(false);
  });
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
      - run: pnpm exec tsc --noEmit
      - run: pnpm test:ci
      - run: pnpm test:coverage
      - run: pnpm build
```

## TanStack Start 特殊考虑

- **routeTree.gen.ts**：自动生成文件，不要手改，coverage exclude 中排除
- **Server Functions**：提取验证逻辑为纯函数，单独测试
- **Loader 测试**：TanStack Start 的 loader 是服务端代码。提取 loader 内的查询/转换逻辑为函数。
- **SSR 组件**：测客户端渲染即可；SSR 路径由 `pnpm build` 的构建验证覆盖
- **无 middleware 概念**：TanStack Start 用 `beforeLoad`，逻辑分散。提取到共享函数中统一测试
