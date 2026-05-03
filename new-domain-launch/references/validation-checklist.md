# 域名验证清单

报告完成前读取。

相关检查全部通过前，不要认为任务完成：

1. Hosting 和 DNS provider 界面显示预期 domain 配置。
2. Vercel + Cloudflare 场景下，Vercel project/domain data 与 Cloudflare zone records 一致。
3. `dig +trace NS <domain>` 显示预期 delegated nameservers；如果 live HTTPS 已证明目标站点可公网访问，可作为替代信号。
4. Public resolvers 返回预期 NS；如果 live HTTPS 已证明目标站点可公网访问，可作为替代信号。
5. 所选 provider 的 authoritative DNS 返回预期 apex 和 `www` records。
6. Vercel 场景下，`www` 是 Vercel 要求的 `CNAME`，不是 `A` record。
7. Hosting provider 标记两个域名都已 attached。
8. `https://APEX_HOST` 返回预期页面内容。
9. 如果预期 redirect，`https://www.DOMAIN` 返回 `301` 到 canonical host。
10. Cloudflare proxy state 和 SSL mode 符合策略。
11. 如果要求邮件转发，Cloudflare Email Routing 已启用，catch-all forwarding 已验证。

如果本地 `dig` 或 public resolver 结果仍旧、受污染，但 Vercel 和 Cloudflare 对记录一致，且真实域名 HTTPS 返回预期页面，则以 live access 作为完成信号，并明确报告 DNS 输出差异。

## Guardrails

- 只有 dashboard 看起来正确时不要结束。
- 只有 DNS provider active、registry delegation 仍旧时不要结束。
- 没有 trace 或 public-resolver checks 时，不要假设传播完成。
- 本地 resolver 与 provider records 或真实访问冲突时，用 Vercel / Cloudflare 界面加直接浏览器或 HTTPS 访问确认。
- 不要猜 provider DNS targets；官方 provider 能返回就用官方值。
- 有凭据时，优先用 registrar API，少用浏览器自动化。
- 如果传播是唯一 blocker 且 live HTTPS 仍不可用，自动重查，不要让用户守着。
