# 跨系统配色命名映射

不同项目用不同的 token 命名。Marc 的配色法则是按**角色**（谁是主 CTA、谁是通用底、谁是主文字）来的，与具体名字无关。先认出项目在用哪套命名，再把 Marc 的角色映射过去即可。

## 一、先检测项目用的是哪套

看 CSS 入口（`globals.css` / `app.css`）和 `components.json`：

- 出现 `--background` / `--foreground` / `--primary-foreground` / `--card` / `--muted-foreground`，或有 `components.json` → **shadcn/ui**
- 出现 `--color-base-100` / `base-content` / `primary-content`，或装了 daisyUI 插件 → **daisyUI**
- 都没有（全新项目）→ 用本 skill 默认（daisyUI 风格角色名），即 `assets/theme.css`

检测命令示例：

```
rg -n "base-content|primary-content|base-100" src app        # daisyUI
rg -n "\-\-(background|foreground|primary-foreground|muted-foreground)" src app   # shadcn
ls components.json 2>/dev/null                                # shadcn 常有
```

匹配到既有体系时，**沿用它的命名**改配色，不要平白引入第二套 token，否则全站要改。

## 二、角色映射表

| Marc 角色 | 用途 | 本 skill / daisyUI | shadcn/ui | 朴素 Tailwind |
|---|---|---|---|---|
| Primary | 唯一主 CTA 底 | `primary` | `primary` | 自定义 `brand` |
| Primary Content | 主 CTA 上的字 | `primary-content` | `primary-foreground` | `brand-foreground` |
| Base | 通用背景 | `base-100` | `background` | `white` / `zinc-50` |
| Base（次级） | 卡片 / 区块 | `base-200` | `card` / `secondary` / `muted` | `zinc-100` |
| Base（更深） | 边框 / 分隔 | `base-300` | `border` / `input` | `zinc-200` |
| Base Content | 标题、主文字 | `base-content` | `foreground` | `zinc-900` |
| Base Content Secondary | 段落、辅助字 | `base-content-secondary` | `muted-foreground` | `zinc-500` |

shadcn 还有 `popover` / `accent` / `ring` / `destructive` 等，按同色相、与对应 foreground 充分对比的原则填即可，不算 Marc 的 4 个核心角色。

## 三、套用 Marc 规则（与命名无关）

无论哪套命名，落地时守同一组规则：

1. 主 CTA 用 Primary，全站只此一个重点色；别处不要再撒第二种彩色。
2. 通用底/字用 Base / Base Content，**避免纯黑 `#000000`**（用深灰、夜蓝、zinc）。
3. 需要更多底色，只在 Base 上做同色相明暗（最多 3 档：shadcn 里就是 `card`/`secondary`/`muted`/`border`）。
4. 段落用 Base Content Secondary（`muted-foreground`），对比要够但弱于主文字。
5. 标题永远用 Base Content（`foreground`）这一最高对比色，不要给标题上彩色——会打断阅读、和主 CTA 抢注意。要点缀关键词用 emphasis 工具类。

## 四、用哪份模板

- 全新项目或 daisyUI → `assets/theme.css`
- shadcn/ui 项目 → `assets/theme-shadcn.css`（已含 `@theme inline` + `:root`/`.dark` + 排版）
- 既有项目只想改色/补排版 → 不整文件替换，按本表把对应 token 的值改成符合规则的颜色，并补上 `references/palette-recipes.md` 里的排版 token。
