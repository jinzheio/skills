---
name: index-onboarding
version: "1.1.0"
description: "当公开站点已经在最终自定义域名上线，且用户要求接入 analytics、baseline metrics、Search Console、sitemap submission、IndexNow、Bing Webmaster Tools 或 Clarity 时使用。触发语包括 set up GSC、connect analytics、do indexing onboarding、域名好了，接搜索和统计。不要用于初始部署或 DNS cutover；先用 upstart-site 或 new-domain-launch。"
---

# 搜索与统计接入

用于最终域名已经可访问后，接入搜索、索引和统计。

这不是部署 skill，而是域名上线后的 onboarding：

1. Umami 或已配置的 web analytics
2. Google Search Console
3. IndexNow
4. Bing Webmaster Tools
5. Microsoft Clarity

推荐顺序：

1. `upstart-site`
2. `new-domain-launch`
3. `index-onboarding`

## 前置条件

硬性前置条件：

1. 站点已经部署
2. 最终自定义域名已确定
3. 最终域名公网可访问

如果站点只在平台临时 URL 上，或自定义域名还在传播，停止并先用 `new-domain-launch`。

某个集成缺少凭据时，只阻塞该集成；继续处理其它集成，并在最后报告 skipped / blocked。

## 输入

- 必填：最终公开域名，例如 `example.com`
- 可选：repo override，用于 site-to-repo 映射缺失时
- 可选：integration config path；默认使用 `$SITE_INTEGRATIONS_CONFIG`

## 目标

尽量完成最终域名的基础 onboarding：

- analytics script 已接入并 live，或说明跳过原因
- Search Console ownership 已验证，或说明 skipped / blocked
- 如果能编辑并部署 repo，`robots.txt` 和 `sitemap.xml` live
- 凭据允许时提交 sitemap
- 安装或确认 IndexNow 已存在
- Bing Webmaster Tools 已添加并验证，或说明 skipped / blocked
- Clarity 从共享 integration map 或 `CLARITY_ID` / `CLARITY_TOKEN` 验证，或说明跳过原因

## 核心规则

- 始终以最终自定义域名为准，不用平台临时 URL。
- 最终域名稳定前，不接 Search Console。
- 最终域名确定前，不生成或发布 IndexNow key。
- 首页 live 但缺 `sitemap.xml` 时，不要声称验证完成。
- IndexNow 不等于自动注册 Bing Webmaster Tools。
- 只读 metrics/reporting 工具不能用于 provision。
- 缺少凭据只阻塞对应集成。
- 一个集成不能跑时，记录 `skipped` 或 `blocked` 后继续。
- 需要代码改动但无法解析 repo 时，跳过 repo-editing，继续 API-only 或 live-site checks。
- 需要部署但缺少部署凭据时，不要声称本地改动已 live。
- Clarity project id 和 token 是项目级；优先共享 integration map，再回退到当前进程或 repo dotenv 中的 `CLARITY_ID` / `CLARITY_TOKEN`。

## 状态词

状态词定义见 repo 根目录 `docs/status-terms.md`。

## Repo 解析

优先读取项目 integration map。如果 `$SITE_INTEGRATIONS_CONFIG` 已设置：

```bash
cat "$SITE_INTEGRATIONS_CONFIG"
```

如果没有映射：

- 从当前 repo 判断 public domain
- 检查 package / framework 配置
- 只在必要时询问用户

## 集成流程

### 1. Live domain check

验证：

- `https://<domain>` 返回目标页面
- `robots.txt` 可访问或需要补
- `sitemap.xml` 可访问或需要补
- canonical / redirect 没有指向临时 host

### 2. Analytics

参考 `references/umami.md`。

确认 tracking script 是否在 live HTML 中出现。缺少凭据或 project mapping 时跳过并说明。

### 3. Google Search Console

参考 `references/search-console.md`。

只在最终域名稳定后处理。能自动验证就自动验证；需要用户完成 ownership 时，说明具体缺口。

### 4. Sitemap / robots

如果 repo 可编辑：

- 补齐或修复 `robots.txt`
- 补齐或修复 `sitemap.xml`
- 确保使用最终域名
- 部署后验证 live URL

### 5. IndexNow

参考 `references/indexnow.md`。如果 repo 还没有 IndexNow，可 handoff 到 `add-indexnow`。

### 6. Bing Webmaster Tools

参考 `references/bing-webmaster.md`。不要把 IndexNow success 当作 Bing ownership success。

### 7. Clarity

参考 `references/clarity.md`。优先从共享配置或 env 获取 project id / token。

## 完成汇报

最后按集成列出：

- `done`
- `skipped`
- `blocked`
- `needs deploy`
- `needs user action`

每项说明依据和下一步。不要把未验证的事项说成完成。
