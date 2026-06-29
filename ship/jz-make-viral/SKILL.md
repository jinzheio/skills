---
name: jz-make-viral
version: "2.0.0"
description: "讨论如何让产品/网站/页面更具传播力、更易转化、更像 viral product 时使用。触发语包括 make it viral、传播力、怎么让它火、为什么没人分享、product principles、定价设计、产品定位、文案写法、landing page 优化、改首页、重写 hero、提升转化率。不用于具体埋点实现（用 jz-track-conversion）。"
---

# 让产品传播起来

综合了 8 个经过验证的高转化改版案例 + 32 Principles of a Viral Product + ClawSimple 实际实施的规律。

不试图一次读完所有 reference。根据讨论主题，读取对应的 reference 文件。

## Reference 索引

| 你在讨论… | 读取 |
|---|---|
| Landing page 结构、首屏、section 顺序、社会证明位置、CTA 安全感 | `references/landing-page-design.md` |
| 文案写法、标题公式、CTA 文案、安全感微文案 | `references/copy-rules.md` |
| Landing page 实施后的设计文档格式 | `references/design-doc-template.md` |
| Landing page 改造完成后的逐项检查 | `references/validation-checklist.md` |
| 定价 tier 设计、免费 vs 付费、一次性 vs 订阅 | `references/pricing.md` |
| 产品定位、只做一件事、名字、竞品对比、founder 出镜 | `references/product-positioning.md` |
| 视觉风格、颜色数量、品牌表达 | `references/visual-brand.md` |

## 核心框架

32 Principles 按功能分组，不是按编号。

### Landing Page 与首屏

把 landing page 当成一次单向销售对话：

1. 先建立共鸣（痛点）
2. 给出解药（产品）
3. 出示证据（评价）
4. 要求成交（CTA）

详细设计流程读 `references/landing-page-design.md`。

### 文案

核心原则：

- 用数字替代形容词。不说"快"，说"3 分钟上线"
- 写只有你能写的文案。竞争对手能 copy-paste 就太泛了
- 客户已经说得很好了。直接引用用户原话
- 五年级学生能懂。复杂性扼杀好奇心
- 不做弱声明。不用 "most"、"many"、"rarely"

详细规则读 `references/copy-rules.md`。

### 定价

- 不要免费计划（不到 3% 转化）
- 定价表要一眼看到（放在 header）
- 三个选择最合适（Popcorn Pricing: Good / Better / Best）
- 一次性付款比订阅好卖 10 倍
- 比别人贵（没人讨论第二便宜的选项）

详细读 `references/pricing.md`。

### 产品定位

- 只做一件事。人们不记得瑞士军刀
- 围绕趋势开发。浪替你完成一半营销
- 做人们从没见过的东西。没人分享 clone
- 名字用已知词。避开生造词
- 卖人类欲望，不卖功能
- 和竞品对比，让人知道为什么切换

详细读 `references/product-positioning.md`。

### 视觉

- 三种颜色：黑色文字 + 白色背景 + 一种 Buy 按钮颜色
- 创始人露脸。人从人买，不买商标

详细读 `references/visual-brand.md`。

## 工作流

当用户讨论或要求改进产品传播力时：

1. **判断话题**：当前在讨论产品哪个方面（文案、定价、定位、landing page、视觉）？
2. **读取对应 reference**，不试图凭记忆回答
3. **对照原则给出具体建议**，每条建议标注依据（来自哪个原则）
4. **如果是 landing page 改造**：收集上下文 → 审计 → 输出设计文档 → 代码实施 → 验证。走 `references/landing-page-design.md` 的完整实施流程

不要一次输出所有 reference 内容。根据当前讨论主题，只读取需要的部分。
