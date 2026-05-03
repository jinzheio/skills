# Umami Analytics

用户使用 Umami，或未选择 analytics provider 但有 Umami 凭据时读取。

## 规则

- 不要硬编码某个 Umami server URL；读取 `UMAMI_BASE_URL`，例如 origin + `/api`。
- 有 `UMAMI_BASE_URL`、`UMAMI_ADMIN_USERNAME`、`UMAMI_ADMIN_PASSWORD` 时，优先 self-hosted Umami admin login。
- 只有 Umami Cloud 或兼容 provider 明确支持 API-key auth 时，才 fallback 到 `UMAMI_API_KEY`。
- 如果既没有 self-hosted login 凭据，也没有 Cloud API key，跳过 Umami 并继续。
- 如果只有 script URL、没有 website id，不要注入不完整脚本。

## Self-hosted Login Pattern

```bash
TOKEN=$(curl -sS "$UMAMI_BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  --data "{\"username\":\"$UMAMI_ADMIN_USERNAME\",\"password\":\"$UMAMI_ADMIN_PASSWORD\"}" \
  | jq -r '.token')

curl -sS "$UMAMI_BASE_URL/me/websites" \
  -H "Authorization: Bearer $TOKEN"
```

如果账号是 admin，且需要创建站点或完整 lookup，使用 documented admin endpoints，例如 `GET <UMAMI_BASE_URL>/admin/websites`。

## 最小目标

- root domain 对应 analytics site/project 存在
- repo 已接入正确 analytics script
- 如代码有改动且有部署凭据，已触发部署
- 最终域名 live HTML 中包含预期 script URL 和 site/project id

静态站点把脚本注入 HTML entry point。env-driven repo 使用 `NEXT_PUBLIC_UMAMI_WEBSITE_ID`、`NEXT_PUBLIC_UMAMI_SCRIPT` 或 repo 既有 analytics env names。
