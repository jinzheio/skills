---
name: jz-setup-testing
description: 测试能力增强。为项目新建/增加/改进测试基础设施，包括补充测试文件、配置覆盖率、补齐 CI 管道、添加测试完整性规则。适用于新项目（尚武测试基建）或已有项目（增强覆盖）。框架支持：Next.js、Astro、TanStack Start。触发短语："加测试"、"写测试"、"提升覆盖率"、"测试基建"、"add tests"、"improve coverage"、"set up testing"、"帮我写测试"、"增加测试"、"补测试"、"测试覆盖率"、"跑不过测试"、"test coverage"、"怎么测试"、"测试怎么配"。
---

# 测试能力增强

为项目建立或增强测试基础设施。支持新项目（从零搭建）和已有项目（补充覆盖）。

## 模式判断

先读项目现状：

- 有 `vitest.config.ts` / `jest.config.ts` / `playwright.config.ts`？→ 增强模式
- 只有 `package.json` 但没有测试配置？→ 新建模式
- 连 `package.json` 都没有？→ 先确认项目框架再继续

## 框架检测

读 `package.json`，按优先级匹配：

1. `dependencies` 或 `devDependencies` 中有 `next` → **Next.js** → 读 `references/nextjs.md`
2. `dependencies` 或 `devDependencies` 中有 `astro` → **Astro** → 读 `references/astro.md`
3. `dependencies` 或 `devDependencies` 中有 `@tanstack/react-start` 或 `@tanstack/start` → **TanStack Start** → 读 `references/tanstack-start.md`
4. 都未匹配 → 按通用前端项目处理，询问用户确认框架

参考文件只在确认框架后按需加载，不在触发时预加载。

## 现状评估

扫描并报告：

| 维度 | 检查内容 |
|------|---------|
| 测试文件 | `find` 统计 `*.test.*` / `*.spec.*` 文件数 |
| 测试运行器 | 检查 vitest/jest/playwright 配置 |
| 覆盖率 | 检查配置中是否有 coverage 块 |
| CI | 检查 `.github/workflows/` 是否有测试相关 workflow |
| 预提交 | 检查是否有 husky/lint-staged/simple-git-hooks |
| 测试规则 | 检查 `CLAUDE.md` 是否有测试完整性条款 |

## 优先级排序

按破坏力确定测试优先级（与代码量无关）：

1. **🔴 真缺的**：计费/支付、认证/权限、数据迁移
2. **🟡 有但不够的**：核心用户旅程（登录→使用→退出）、错误页面、API 路由守卫
3. **🟢 可以不测的**：纯静态页、第三方 SDK 封装、马上要改的 UI

## 实施流程

### 新项目（新建模式）

1. 安装依赖：`vitest` + `@testing-library/react`（如 React）+ `happy-dom` + `@vitest/coverage-v8`
2. 创建 `vitest.config.ts`
3. 创建 `src/test-setup.ts`
4. 添加 `package.json` scripts
5. 创建 `.github/workflows/ci.yml`
6. 更新 `CLAUDE.md` 添加测试完整性规则

### 已有项目（增强模式）

1. 识别覆盖盲区：对比源文件与测试文件
2. 优先补计费/认证/部署等关键路径
3. 遵循项目现有测试模式（mock 风格、断言风格、文件命名）
4. 如需补齐 CI：创建或修复 `.github/workflows/ci.yml`
5. 更新覆盖率基线：跑 `test:coverage` 后同步 `vitest.config.ts` 中的 thresholds

## 原则

- **Confidence > Coverage**：测关键路径，不追求数字
- **遵循现有模式**：不要引入新的测试风格或框架
- **测试是行为契约**：不为了让测试通过而修改正确的测试
- **禁止在 E2E 中修改应用状态**：禁止 `page.evaluate()`、`localStorage.setItem()`、`window.* = true`
- **边界案例让 AI 批量生成，人工筛选**：AI 擅长边界输入，人擅长判断有意义场景

## CLAUDE.md 测试规则

无论新建还是增强，确保项目 `CLAUDE.md` 包含：

1. 测试是行为契约——测试描述系统应该做什么
2. 禁止在测试中修改应用状态（`page.evaluate` / `localStorage` / `window.*` 等）
3. 测试数量守卫——不删测试、不缩小覆盖范围
4. 先写失败测试——修 bug 前先写复现测试
5. Producer-Verifier 分离——写代码的 Agent 不审查自己的测试
