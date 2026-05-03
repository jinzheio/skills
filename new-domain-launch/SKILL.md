---
name: new-domain-launch
version: "1.1.1"
description: "当用户已有可用部署、想连接自定义域名时使用，包括 connect this domain、绑定域名、set up DNS、make www redirect、enable HTTPS。覆盖 registrar nameservers、DNS provider records、hosting-platform domain binding、TLS、apex/www 跳转，以及用户要求时的邮箱转发。站点还没有可用部署时不要使用；先用 upstart-site。"
---

# new-domain-launch

用于站点已经部署后，把自定义域名连到公开互联网。

典型顺序：

1. 站点已经有临时 host 或平台 URL。
2. 用户提供新域名。
3. 本 skill 连接 registrar、DNS provider 和 hosting provider，直到域名可访问。

不要把“记录已创建”或“平台显示 verified”当作完成。完成标准是公网可访问。

## 目标

- apex host 解析正确
- `www` 符合预期跳转策略
- HTTPS 可用
- live site 可从公网访问
- 用户要求时，入站邮件转发可用

## 默认策略

除非用户另有要求：

- apex 域名为 canonical，例如 `example.com`
- `www.example.com` 用 `301` 跳转到 apex
- Vercel 类托管中，如果 provider 返回 CNAME target，`www` 使用 `CNAME`
- 不要把 apex 的 `A` 记录照搬到 `www`
- 使用 Cloudflare 时，先确认 origin，再开启 orange-cloud proxy
- Cloudflare 代理有效 HTTPS origin 时，SSL/TLS 使用 `Full (strict)`

## 不要漏掉

- Vercel + Cloudflare 场景下，`www` 应使用 provider 推荐的 `CNAME`。
- Cloudflare proxy 只用于 Web records，例如 `A`、`AAAA`、`CNAME`。
- 不要 proxy 或改写 `MX`、SPF、DKIM、DMARC、Cloudflare Email Routing TXT。
- Cloudflare 是目标 DNS 层时，origin 验证后再开启 orange-cloud。
- origin 有有效证书时，Cloudflare SSL/TLS 设为 `Full (strict)`。
- 代理开启后重新验证 HTTPS。DNS-only 可用不代表 proxy 后也可用。

## 前置条件

改 DNS 前确认：

1. 项目已经在托管平台有可用部署。
2. 已确认 canonical host：
   - apex only
   - `www` only
   - apex canonical + `www` redirect
3. 已确认三个系统：
   - registrar，例如 Spaceship
   - DNS provider，常见是 Cloudflare
   - hosting provider，常见是 Vercel

如果站点还没部署，停止并先走部署流程。

## Source of Truth

配置以平台 API 和 dashboard 为准：

- DNS intent 来自 hosting provider 和 DNS provider。
- Vercel + Cloudflare 时，优先信任 Vercel domain/project inspection 和 Cloudflare zone records。
- 可访问性通过加载公网 URL 并收到预期页面内容证明。
- `dig` 等本地 DNS 输出只能作为辅助证据，可能受缓存或本地网络污染影响。

## 流程

### 1. 计划

改 registrar、DNS、hosting、TLS 或 email 前，先给出计划：

- domain 和 canonical host
- registrar、DNS provider、hosting provider
- apex / `www` 目标记录
- proxy 策略
- HTTPS 验证方式
- 是否包含 email routing

### 2. 检查当前状态

使用可用 CLI / API / dashboard 查询：

- registrar nameserver
- DNS zone records
- hosting provider domain binding
- HTTPS 状态
- 当前公网响应

优先使用 provider API。不要只依赖本地 resolver。

### 3. 设置 DNS 和托管平台

按 provider 的目标记录设置：

- apex：通常是 `A` 或 provider 指定记录
- `www`：通常是 `CNAME`
- 删除冲突记录
- 确认 hosting provider 已绑定域名
- 等待 provider 显示可验证状态

如果 Cloudflare 代理会影响验证，先用 DNS-only 完成 origin 验证，再开启 proxy。

### 4. HTTPS 与跳转

验证：

- `https://apex`
- `https://www`
- canonical redirect
- HTTP 到 HTTPS
- 证书链
- 页面内容是否是目标站点

### 5. 邮箱转发

只有用户要求时处理。先读 `references/email-routing.md`。

不要为了网站上线改坏现有邮件记录。

### 6. 验收

用 `references/validation-checklist.md` 做最终检查。

汇报时包括：

- 最终 DNS 记录
- canonical host 和 redirect 结果
- HTTPS 结果
- Cloudflare proxy 状态
- 邮箱转发是否处理
- 仍在传播或需要用户确认的事项

## 相关引用

- 邮件转发：`references/email-routing.md`
- 验证清单：`references/validation-checklist.md`
