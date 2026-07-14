---
name: jz-setup-mailgun-domain
description: 初始化 Mailgun 发信域名并生成项目配置。用于用户给出一个域名，要求新增 Mailgun domain、通过 Cloudflare 写入 SPF/DKIM/Tracking/MX、等待验证、创建 Domain Sending Key，或获取 MAILGUN_API_KEY、MAILGUN_DOMAIN、MAILGUN_API_BASE_URL、EMAIL_FROM。默认使用 Mailgun US；任何写操作前必须让用户确认地区、最终域名和 From 地址。域名不是以 mg. 或 mail. 开头时，先提醒 MX 冲突风险并取得显式确认。
---

# Mailgun 发信域名初始化

输入一个域名后，把 Mailgun、Cloudflare DNS 和项目发信配置接好。

## 开始前确认

在任何外部写操作前，把以下信息发给用户并等待明确确认：

- 最终 Mailgun domain
- Mailgun 地区和 API base URL
- `EMAIL_FROM`，默认 `noreply@<Mailgun domain>`
- Cloudflare 权限：目标 Zone 的 `Zone Read + DNS Write`
- 将写入当前项目的 `.dev.vars` 和 `.env`

默认地区：

```text
US → https://api.mailgun.net
```

用户没有指定地区时，也必须确认 US 后再开始。不要把默认值当成用户已经确认。

### MX 风险确认

最终域名的第一段严格等于 `mg` 或 `mail` 时，不需要额外确认 MX 风险，例如：

```text
mg.example.com
mail.example.com
```

其他前缀和裸域名不做 Public Suffix 猜测。先说明 Mailgun 的 MX 记录可能和已有邮箱服务冲突，并建议改用 `mg.<domain>`。用户坚持使用原域名时，再执行脚本的 `--confirm-mx-risk`；不要自行决定。

### From 地址处理

默认使用：

```text
noreply@<Mailgun domain>
```

用户可以指定显示名称，例如 `Example <noreply@mg.example.com>`。From 使用其他域名时，提醒用户检查 DMARC alignment，得到确认后才使用 `--allow-custom-from-domain`。

开始前检查 `.dev.vars` 和 `.env` 中已有的 `EMAIL_FROM`：

- 已有值和最终值相同：复用。
- 只有一个文件有值：确认最终值后同步到两个文件。
- 已有值不同：先让用户选择保留或替换；确认替换后才使用 `--replace-email-from`。

## 凭证

从当前项目的 `.dev.vars`、`.env`、`.env.local`、`.env.production`、`.env.development` 读取：

- `MAILGUN_PRIMARY_API_KEY`：只用于域名和 key 管理，不写入应用配置
- `CLOUDFLARE_DNS_API_TOKEN`，其次才是 `CLOUDFLARE_API_TOKEN`

调用 `$jz-create-cloudflare-token` 新建 token 时还需要 `CLOUDFLARE_ACCOUNT_ID`。

Mailgun Primary Key 也可以放在 `~/.config/skills/jz-setup-mailgun-domain/.env`。不要把 Cloudflare bootstrap token 当作 DNS token 使用。

Cloudflare token 缺失或没有目标 Zone 权限时，使用 `$jz-create-cloudflare-token` 创建仅限目标 Zone 的 `Zone Read + DNS Write` token，再保存为项目的 `CLOUDFLARE_DNS_API_TOKEN`。初次确认已经列明该权限集时，不重复询问。

任何时候都不要输出 secret、Authorization header 或完整 API 响应。

## 执行

用户确认后，在目标项目目录运行：

```bash
uv run python <skill-dir>/scripts/setup_mailgun_domain.py \
  <confirmed-domain> \
  --region us \
  --confirmed-region us \
  --email-from 'noreply@<confirmed-domain>'
```

EU 区改为：

```bash
uv run python <skill-dir>/scripts/setup_mailgun_domain.py \
  <confirmed-domain> \
  --region eu \
  --confirmed-region eu \
  --email-from 'noreply@<confirmed-domain>'
```

用户明确接受非 `mg.` / `mail.` 域名的 MX 风险时追加：

```text
--confirm-mx-risk
```

脚本会：

1. Git 项目中确认 `.env` 和 `.dev.vars` 当前未被跟踪，并且会被 Git 忽略；非 Git 项目只执行文件写入，不声称有 Git ignore 保护。
2. 验证 Cloudflare token 能访问目标 Zone。
3. 幂等创建 Mailgun domain，并启用 Automatic Sender Security。
4. 读取 Mailgun 返回的 DNS 记录，不使用固定模板。
5. 幂等创建 Cloudflare DNS；遇到冲突记录时停止，不覆盖。
6. 触发 Mailgun verify，等待连续两次 `active`。
7. 复用项目中有效的 Domain Sending Key；没有时创建新 key。
8. 把以下配置同步到 `.dev.vars` 和 `.env`：

```text
MAILGUN_API_KEY=<domain-sending-key>
MAILGUN_DOMAIN=<confirmed-domain>
MAILGUN_API_BASE_URL=<confirmed-base-url>
EMAIL_FROM=<confirmed-from-address>
```

脚本只报告 key ID 和配置位置，不显示 key。创建 key 后如果验证或写文件失败，脚本会撤销该 key。

## 完成标准

只有同时满足以下条件才报告完成：

- Mailgun domain 连续两次为 `active`
- Mailgun 返回的 DNS 记录都存在于 Cloudflare
- Mailgun 当前要求的记录均为 `valid`
- Domain Sending Key 能通过发送端点鉴权；验证请求不得真正发送邮件
- `.dev.vars` 和 `.env` 中四项发信配置一致
- Git 项目中的两个文件仍未被跟踪，并且会被 Git 忽略

Automatic Sender Security 可能保留一条 `valid` 但未激活的备用 DKIM。域名为 `active` 时，不要把备用 key 未激活误判为失败。

## 汇报

说明：

- 最终 domain、地区、base URL、`EMAIL_FROM`
- Mailgun 状态
- 创建/复用的 DNS 记录数量
- Sending Key 是新建还是复用，并给出 key ID（如果 API 返回）
- 写入了哪些配置文件和变量名
- 是否还有传播中的记录

不要显示 `MAILGUN_API_KEY`、Primary Key 或 Cloudflare token。
