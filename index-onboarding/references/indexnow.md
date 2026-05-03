# IndexNow Onboarding

在域名上线后的 onboarding 流程中处理 IndexNow 时读取。

把 IndexNow 当作域名后的索引配置，不是核心部署步骤。

## 流程

1. 检查 repo 是否已有 IndexNow 实现。
2. 如果没有，使用本 skill pack 的 `add-indexnow`。
3. 只为最终域名生成新的 host-scoped key。
4. 确认 verification file 已在最终域名上提供。
5. 确认 repo 有可复用的 collect-and-submit 路径。
6. 使用真实最终 host 验证，不用临时部署 URL。

## 最小目标

- key file 在最终 host 上公开可访问
- repo 有可复用 submission workflow
- IndexNow 配置匹配最终 canonical domain

不要复用绑定临时 host 的 key。如果已有实现，更新它，不要重复创建脚本。

如果无法解析或编辑 repo，报告 IndexNow 为 `skipped`，继续 Bing Webmaster Tools。
