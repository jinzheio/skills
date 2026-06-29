# 配色法则与强调用法

来源：Marc Lou《Design beautiful websites to sell your product — Colors》。
核心思想：**设计不是创意，是规则**。代码出身、审美一般也能照规则做出能转化的落地页。

## 一、四色起步（Rule #1：少用颜色）

颜色像啤酒，超过 3、4 种就乱了。落地页只要 1 个主 CTA，其余都是次要。

最小调色板 = 4 个颜色，分两组：

| 角色 | token | 用途 |
|---|---|---|
| Primary | `--color-primary` | 唯一主 CTA（买产品的按钮） |
| Primary Content | `--color-primary-content` | 主色块上的文字 |
| Base | `--color-base-100` | 几乎所有背景 |
| Base Content | `--color-base-content` | 几乎所有文字 |

两条硬规则：

1. 内容色要和背景色**对比充分**。
2. **避免纯黑 `#000000`**，改用深灰、夜蓝、zinc——更高级、不刺眼。

## 二、扩展 Base（需要更多颜色时）

只在 Base 上找**更深或更浅**的同色相色，最多再加 3 档：

- `--color-base-200`：次级区块 / 卡片
- `--color-base-300`：边框 / 分隔线

规则：

1. 每个 Base 都要和 Base Content 对比充分。
2. 所有 Base **保持相近色相**（例如全部偏黄、或全部偏蓝灰）。

## 三、文字层级

加一个 `--color-base-content-secondary` 做文字层级（标题下的支撑段落）：

- 它要和 Base 对比充分，但**弱于** Base Content。

一般规则：

- 标题 → `text-base-content`
- 段落 → `text-base-content-secondary`
- CTA → `bg-primary text-primary-content`

## 四、现成调色板配方

替换 `assets/theme.css` 里 `@theme` 中的占位色即可。每套都遵守"避免纯黑 + 同色相 Base"。

### Indigo / Zinc（默认，干净 SaaS 感）
```
--color-primary: #4f46e5;          --color-primary-content: #ffffff;
--color-base-100: #ffffff;         --color-base-200: #f4f4f5;  --color-base-300: #e4e4e7;
--color-base-content: #18181b;     --color-base-content-secondary: #52525b;
```

### Amber / Stone（温暖，偏黄色相，贴近 Marc 原文插图）
```
--color-primary: #f59e0b;          --color-primary-content: #1c1917;
--color-base-100: #fffdf7;         --color-base-200: #f5f0e6;  --color-base-300: #e7ddc8;
--color-base-content: #292524;     --color-base-content-secondary: #6b5f4f;
```

### Emerald / Slate（夜蓝背景，深色主题）
```
--color-primary: #10b981;          --color-primary-content: #04140d;
--color-base-100: #0f172a;         --color-base-200: #1e293b;  --color-base-300: #334155;
--color-base-content: #f1f5f9;     --color-base-content-secondary: #94a3b8;
```

### Rose / Neutral（克制的高对比）
```
--color-primary: #e11d48;          --color-primary-content: #ffffff;
--color-base-100: #ffffff;         --color-base-200: #f5f5f5;  --color-base-300: #e5e5e5;
--color-base-content: #171717;     --color-base-content-secondary: #525252;
```

选色提示：主色用品牌色；Base 选一个接近中性但带轻微色相倾向的灰；深色主题把 base-100 设成夜蓝而非纯黑。

## 五、强调效果（标题关键词重音）

`assets/theme.css` 内置三个 `@utility`，对应 Marc 插图里的"重点词"做法。给关键词包一个 `<span>` 即可，**一句话里别叠超过一个**。

### 1. 平行四边形高亮 `em-mark`
关键词后铺一块斜切主色块，文字反白——最像马克笔涂抹。
```html
<h1 class="text-base-content">
  Ship your startup <span class="em-mark">faster</span>
</h1>
```

### 2. 虚线下划线 `em-underline`
关键词下一条主色虚线，轻量、不抢戏。
```html
<h1 class="text-base-content">
  The <span class="em-underline">only</span> tool you need
</h1>
```

### 3. 荧光笔涂抹 `em-highlight`
关键词底部一道粗主色高亮，背景在文字之后。
```html
<h1 class="text-base-content">
  Grow your <span class="em-highlight">revenue</span>
</h1>
```

### 换强调色
三个 utility 默认都用 `--color-primary`。若想让强调色独立于主 CTA，在 `@theme` 里加一个变量（如 `--color-accent`），再把 `theme.css` 强调段落里的 `var(--color-primary)` 换成 `var(--color-accent)`。

### 微调
- 倾斜角度：改 `em-mark` 的 `skewX(-12deg) rotate(-1.5deg)`。
- 高亮粗细 / 位置：改 `em-highlight` 的 `background-size`（高度）和 `background-position`。
- 虚线粗细：改 `em-underline` 的 `text-decoration-thickness`。

## 六、排版（Rule #2：标题要大、粗、紧、短）

来源：Marc Lou《Design beautiful websites — Headlines》。这是配色之外另一半，clawsimple 这类"配色对了还是不好看"多半就缺这块。Marc 给的是**准确值**：

| 维度 | 正文默认 | 标题（Marc 的值） |
|---|---|---|
| 字号 | 16px | h1 60px / h2 48px（桌面）；移动端 32–40px |
| 字重 | 400 | 700–900（全站统一，本模板取 800） |
| 字距 letter-spacing | 0 | **减 -0.4px** |
| 行高 line-height | ~1.5–1.6（易读默认） | **收到 1** |
| 长度 | 每行 ≤ ~65ch | ≤ 70 字符、≤ 2 行 |

补充规则：

- 字号系统定一套就全站统一（Marc 自己：h1 60 / h2 48）。模板用 `clamp()` 让它在 32→60px 间流式响应，省去手写断点。
- 标题超过 ~1000px 宽就换行，找**语义断点**（按意思断句）而不是视觉断点。
- 标题颜色用 Base Content（最高对比），**不要再上彩色**；要强调个别词用第五节的 emphasis（或仅对数字用 primary）。
- 每个 section 只放 1 个标题 + 1 段 + 1 图 + 1 按钮。

### 模板提供的排版 token

`assets/theme.css`（及 shadcn 版）已在 `@theme` 内定义：

- `text-h1` / `text-h2`：一次性带上 字号(clamp 流式) + 行高(1) + 字距(-0.4px) + 字重(800)
- `tracking-headline`（-0.4px）/ `leading-headline`（1）：手动微调用
- `@layer base` 给 `h1/h2/h3` 设了兜底字距/行高/字重，`body` 行高 1.6，`p` 限宽 65ch

用法：

```html
<h1 class="text-h1 text-base-content">
  Ship your startup <span class="em-mark">faster</span>
</h1>
<p class="text-base-content-secondary">A clear supporting sentence.</p>
```

> 注：`-0.4px` 字距、`line-height: 1`、字号 60/48 与移动端 32–40px、字重 700–900、70 字符/2 行——这些是 Marc 文章里的原值。正文行高 1.5–1.6 是通用易读默认，Marc 的标题文章未给正文行高的具体数。

## 七、用 4 色能搭出的东西

按上面规则，4 色足以做出按钮、卡片、价格表、整页落地页。真正的设计师能驾驭多色；如果你审美一般，**就守住规则、少用颜色**——目标是让用户不困惑、直接下单。
