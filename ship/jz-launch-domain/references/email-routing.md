# Cloudflare Email Routing

仅当用户明确要求入站域名邮件转发时读取。

## 前置条件

- 最终自定义域名已委托到 Cloudflare
- Cloudflare zone 已 active
- 已提供或已配置转发目标邮箱
- Cloudflare token 或浏览器 session 有 Email Routing 权限

## 流程

1. 检查 zone 的 Email Routing 状态。
2. 如果未启用，启用 Email Routing，并让 Cloudflare 添加 MX、SPF、DKIM records。
3. 检查目标邮箱是否已经是 verified Email Routing address。
4. 如果未验证，创建 destination address 并完成邮箱验证。
5. 将 catch-all rule 从 `drop` 改为 `forward`。
6. 验证 catch-all rule 指向目标邮箱。
7. 如果有可用 sender，发送真实测试邮件并报告结果。

## 完成标准

邮件转发完成必须满足：

- Email Routing 为 `enabled`
- MX records 指向 Cloudflare mail exchangers
- 必需 SPF 和 DKIM records 存在
- catch-all rule 已启用并转发到目标邮箱
- 如有 sender，test send 状态已知

如果 API token scope 不足，改用浏览器自动化，或报告缺少的精确权限。
