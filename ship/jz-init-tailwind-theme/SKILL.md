---
name: jz-init-tailwind-theme
version: "1.1.0"
description: "当用户要新建或初始化 Tailwind 主题/配置、设置网站或落地页配色与排版、定义 design tokens、或觉得现有配色/字体不好看想按规则调时使用，统一采用 Tailwind v4 的 CSS-first 写法（@import \"tailwindcss\" + @theme，不写 tailwind.config.js）。典型触发：new tailwind config、初始化 tailwind 主题、setup colors、配色方案、设计系统、标题字号/行高/字距/排版、给标题关键词加强调（虚线下划线 / 平行四边形高亮 / 荧光笔涂抹）。配色与排版遵循 Marc Lou 的法则，并兼容 shadcn/ui 与 daisyUI 的命名。边界：默认输出 v4 CSS-first 主题，仅当用户明确要 v3 / tailwind.config.js 时才降级；不负责整页布局、组件库选型或 Tailwind 安装本身。"
---

# 初始化 / 调整 Tailwind v4 主题（配色 + 排版 + 强调）

新建 Tailwind 配置/主题，或按规则修正已有主题时用本 skill。产出是一个 **Tailwind v4 CSS-first 主题文件**：用 `@import "tailwindcss"` + `@theme` 定义 design tokens，而不是老的 `tailwind.config.js`。

依据 Marc Lou《Design beautiful websites》系列两条法则：

- **配色（Colors）**：少用颜色，4 色起步。
- **排版（Headlines）**：标题要大、粗、紧、短。这是"配色没问题但还是不好看"的常见缺口，别只做颜色。

并内置三种关键词强调效果。

## 为什么是 v4 CSS-first

Tailwind v4 把主题配置从 JS 移到了 CSS：颜色、字体、字号都用 `@theme { --color-* / --text-* … }` 声明，Tailwind 据此自动生成 `bg-*`、`text-*`、`tracking-*`、`leading-*` 等工具类。除非用户明确点名 v3 或 `tailwind.config.js`，一律按 v4 CSS-first 输出。

## 工作流

### 1. 先确认意图 + 检测既有体系

简短对齐（用户没说就用默认）：

- 配色基调：品牌主色 / 风格。默认 indigo + zinc。
- 文件落点：CSS 入口（如 `src/app.css`、`app/globals.css`）。默认新建 `app.css`。
- 是否要排版 token 与关键词强调效果。默认都带上。

**关键：先认出项目已在用哪套配色命名**，避免平白引入第二套 token。读 `references/color-systems.md` 检测：

- shadcn/ui（`--background` / `--foreground` / `--primary-foreground`，或有 `components.json`）→ 用 `assets/theme-shadcn.css`
- daisyUI（`base-100` / `base-content` / `primary-content`）或全新项目 → 用 `assets/theme.css`
- 已有主题只想改色/补排版 → 不整文件替换，按映射表改对应 token 的值并补排版 token

如果用户明确要 v3 / `tailwind.config.js`，停下确认后再按旧格式手工转换。

### 2. 选配色（Marc 4 色法则）

读 `references/palette-recipes.md`，按角色定色：

- Primary / Primary Content → 唯一主 CTA
- Base / Base Content → 其它一切

硬规则：内容色与背景充分对比；**避免纯黑 `#000000`**（用深灰 / 夜蓝 / zinc）；要更多底色只在 Base 上做同色相明暗（最多 3 档）；段落用 Base Content Secondary。`palette-recipes.md` 有 4 套现成配方；跨命名映射见 `color-systems.md`。

### 3. 定排版（Marc Headlines 法则）—— 不要跳过

读 `references/palette-recipes.md` 第六节。Marc 的准确值：

- 标题字号 h1 60px / h2 48px（桌面），移动端 32–40px
- 标题字重 700–900（全站统一）
- 标题字距 **letter-spacing -0.4px**
- 标题行高 **line-height 1**
- 标题 ≤ 70 字符、≤ 2 行；颜色用 Base Content，不上彩色

模板已把这些做成 `text-h1` / `text-h2`（clamp 流式，带字号+行高+字距+字重）和 `tracking-headline` / `leading-headline`，并在 `@layer base` 给 `h1/h2/h3` 设了兜底字距/行高/字重、`body` 行高 1.6、`p` 限宽 65ch。

### 4. 生成 / 修改主题文件

新项目：复制对应模板到 CSS 入口，替换配色。
已有项目（如 shadcn）：在既有 `@theme` 内补排版 token，在 `@layer base` 补标题/正文规则，按映射表校正配色——不要新引入一套命名。不需要强调效果就删掉 emphasis 段落。

### 5. 给出用法

- 标题 `text-h1` / `text-h2` + `text-base-content`（shadcn：`text-foreground`）
- 段落 `text-base-content-secondary`（shadcn：`text-muted-foreground`）
- CTA `bg-primary text-primary-content`（shadcn：`text-primary-foreground`）
- 关键词强调：包 `<span class="em-mark">`（或 `em-underline` / `em-highlight`），一句里别叠超过一个

### 6. 验证

静态自检：`@import "tailwindcss"` 在最前、每个 `--color-*` 有值、`@utility` 名称合法。条件允许时用 v4 CLI 实编一次，确认无报错且生成了 `text-h1`、`em-mark` 等类：

```
npx @tailwindcss/cli -i app.css -o /tmp/out.css   # 配合用到这些类的示例 HTML
```

## 关键规则

- 默认 v4 CSS-first（`@theme`），不主动写 `tailwind.config.js`。
- 沿用项目既有配色命名（shadcn / daisyUI），别引入第二套 token。
- 守住 4 色起步；颜色超过 3、4 种会让用户困惑、降低转化。
- 永远不用纯黑 `#000000`。
- 排版和配色一样重要：标题大/粗/紧（-0.4px、行高 1）、短（≤70 字符/2 行），别只调颜色。
- 标题不上彩色；强调用 emphasis 工具类点缀，克制使用。
- 不处理 Tailwind 安装、整页布局或组件库选型——只产出主题。

## 资源

- `assets/theme.css` — daisyUI/全新项目模板（配色 + 排版 + 强调）
- `assets/theme-shadcn.css` — shadcn/ui 命名版模板（配色 + 排版 + 强调）
- `references/palette-recipes.md` — 配色法则、4 套配方、排版准确值、强调 HTML 用法
- `references/color-systems.md` — shadcn / daisyUI / 朴素 Tailwind 的命名映射与检测
