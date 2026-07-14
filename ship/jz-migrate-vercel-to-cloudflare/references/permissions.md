# Cloudflare 权限

使用能完成迁移的最小 token。

常见 Workers 迁移需要：

- Account: Workers Scripts Edit
- Account: Workers Routes Edit
- Account: D1 Edit
- Account: R2 Edit
- Account: Queues Edit
- Account: Vectorize Edit
- Zone: 目标域名的 Zone Read
- Zone: 目标域名的 DNS Edit
- Zone: 目标域名的 Workers Routes Edit

错误对应关系：

- Vectorize list/create 返回 `Authentication error [code: 10000]`：缺 Vectorize 权限。
- Worker 上传成功，但 `/workers/routes` 失败：缺 zone 级 Workers Routes 权限。
- custom domain 发布在 `/domains/records` 失败：缺 custom domain/DNS 记录权限，或同名 DNS 记录冲突。
