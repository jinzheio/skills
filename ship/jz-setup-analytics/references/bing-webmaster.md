# Bing Webmaster Tools

处理 Bing Webmaster Tools onboarding 时读取。

IndexNow URL submission 本身不会让站点出现在 Bing Webmaster Tools 中。

## 规则

- 如果有 `BING_WEBMASTER_API_KEY`，优先走 API，不走手动浏览器导入。
- 用户明确要求时，可以从 Google Search Console import，但这是可选项。
- 如果缺少 Bing 凭据和浏览器访问，把 Bing Webmaster Tools 标记为 `skipped`，继续 Clarity。

## 推荐 API 流程

1. 调 `GetUserSites` 检查最终域名是否已存在。
2. 缺失时，对最终 canonical URL 调 `AddSite`，例如 `https://example.com/`。
3. 读取返回 metadata，尤其是：
   - `AuthenticationCode`
   - `DnsVerificationCode`
   - `IsVerified`
4. 静态或 repo-controlled 站点优先使用 HTML meta 验证：
   - 在 live homepage head 加 `<meta name="msvalidate.01" content="<AuthenticationCode>" />`
   - 如改了代码且有部署凭据，部署 repo
5. verification token live 后调 `VerifySite`。
6. 重查 `GetUserSites`，直到 `IsVerified = true`；如果 `VerifySite` 成功但状态未刷新，报告刷新延迟。
7. 通过 `SubmitFeed` 提交 sitemap。
8. 可选：通过 `SubmitUrl` 提交 homepage 或 changed URLs。

## 最小目标

- site 出现在拥有账号的 Bing Webmaster Tools 中
- verification state 已知
- sitemap submission state 已知

使用最终 canonical URL 验证，并保持 trailing slash 一致。
