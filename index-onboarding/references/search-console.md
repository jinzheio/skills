# Google Search Console

处理 Search Console ownership、robots、sitemap 和 sitemap submission 时读取。

## 缺少凭据

如果缺少 Google 凭据：

1. 仍然检查 `robots.txt` 和 `sitemap.xml` 是否 live。
2. 如果能解析 repo，需要时添加或修复 `robots.txt` 和 `sitemap.xml`。
3. 将 Search Console ownership 和 sitemap submission 报告为 `skipped`。
4. 继续 IndexNow。

## GCP 与 ADC

Search Console 和 Site Verification API 调用需要两件事：

- 可以拥有或验证站点的 Google identity
- API 调用使用的 GCP quota project

不要静默使用当前 `gcloud config get-value project` 作为 quota project；它可能属于无关 app。

推荐 quota-project 流程：

1. 选择或创建专用项目，例如 `<site>-indexing` 或 `<org>-site-indexing`。
2. 在该项目启用：
   - `searchconsole.googleapis.com`
   - `siteverification.googleapis.com`
   - `serviceusage.googleapis.com`
3. 设置 ADC quota project：

```bash
gcloud auth application-default set-quota-project <project-id>
```

4. 用 Search Console 和 Site Verification scopes mint access token：

```bash
gcloud auth application-default print-access-token \
  --scopes=https://www.googleapis.com/auth/webmasters,https://www.googleapis.com/auth/siteverification \
  --billing-project=<project-id>
```

5. 使用 user ADC tokens 调 Google API 时带上 `X-Goog-User-Project: <project-id>`。

如果允许创建项目，优先创建专用项目，不借用无关现有项目。

如果 billing-account linking 因项目 quota 失败，仍尝试启用 APIs 并设置 ADC quota project。API enablement 和 quota-project 权限有效时，Search Console 与 Site Verification 可在未绑定 billing 的情况下工作。

失败处理：

- `requires a quota project`：设置 ADC quota project 或发送 `X-Goog-User-Project`。
- `caller lacks serviceusage.services.use`：quota project 选错，或用户缺 Service Usage Consumer 权限。使用 Google 账号拥有的专用项目，或授予权限。
- `SERVICE_DISABLED`：在 quota project 启用 API。
- billing quota failures 不等于 Search Console permission failures。

## 推荐流程

以最终域名为 property source of truth。

1. 检查 `sc-domain:<domain>` 是否已经存在。
2. 缺失时，调用 Google Site Verification API `getToken`，method 为 `DNS_TXT`。
3. 在 DNS 添加 TXT token。
4. 调 Site Verification API `insert` 验证 ownership。
5. 调 Search Console API `sites.add` 添加 `sc-domain:<domain>`。
6. 确认 live site 提供：
   - `robots.txt`
   - `sitemap.xml`
7. 用 Search Console API 提交 sitemap。

单独 verification 不够。如果 homepage 是 `200` 但 `sitemap.xml` 是 `404`，Search Console onboarding 报告为 `partial`。
