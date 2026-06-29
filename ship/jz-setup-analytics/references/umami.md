# Umami Analytics

用户使用 Umami，或未选择 analytics provider 但有 Umami 凭据时读取。

## 规则

- 查找凭据时使用 `infra-credential-lookup` 顺序：当前项目 env、团队约定的本机未跟踪配置、安全存储或用户级工具，最后才使用浏览器登录态。
- 不要硬编码某个 Umami server URL；优先读取 `UMAMI_BASE_URL`，可接受 origin（如 `https://umami.example.com`）或 API base（如 `https://umami.example.com/api`）。
- 有 `UMAMI_BASE_URL`、`UMAMI_ADMIN_USERNAME`、`UMAMI_ADMIN_PASSWORD` 时，优先 self-hosted Umami admin login。缺少任一变量时，再查团队约定的 admin fallback 凭据。
- 只有 Umami Cloud 或兼容 provider 明确支持 API-key auth 时，才 fallback 到 `UMAMI_API_KEY`；不要因为 `UMAMI_API_KEY` 为空就停止。
- 如果既没有 self-hosted login 凭据，也没有 Cloud API key，跳过 Umami 并继续。
- 如果只有 script URL、没有 website id，不要注入不完整脚本。
- 注入前端时优先使用 `UMAMI_SCRIPT_URL`，并把 website id 写入项目采用的 public env 名称，例如 Vite 项目用 `VITE_UMAMI_SCRIPT_URL` 和 `VITE_UMAMI_WEBSITE_ID`。

## API Base 归一化

`UMAMI_BASE_URL` 可能是 origin，也可能已经包含 `/api`。调用 API 前归一化：

```bash
UMAMI_API_BASE="${UMAMI_BASE_URL%/}"
case "$UMAMI_API_BASE" in
  */api) ;;
  *) UMAMI_API_BASE="$UMAMI_API_BASE/api" ;;
esac
```

## Self-hosted Login Pattern

```bash
TOKEN=$(curl -sS "$UMAMI_API_BASE/auth/login" \
  -H "Content-Type: application/json" \
  --data "{\"username\":\"$UMAMI_ADMIN_USERNAME\",\"password\":\"$UMAMI_ADMIN_PASSWORD\"}" \
  | jq -r '.token')

curl -sS "$UMAMI_API_BASE/websites" \
  -H "Authorization: Bearer $TOKEN"
```

如果账号是 admin，且需要创建站点或完整 lookup，优先使用 documented API，例如 `GET <UMAMI_API_BASE>/websites` 和 `POST <UMAMI_API_BASE>/websites`。不同 Umami 版本的响应字段可能不同，创建或查询后必须从响应或列表中确认 website id。

## 最小目标

- root domain 对应 analytics site/project 存在
- repo 已接入正确 analytics script
- 如代码有改动且有部署凭据，已触发部署
- 最终域名 live HTML 中包含预期 script URL 和 site/project id

静态站点把脚本注入 HTML entry point。env-driven repo 使用 `NEXT_PUBLIC_UMAMI_WEBSITE_ID`、`NEXT_PUBLIC_UMAMI_SCRIPT` 或 repo 既有 analytics env names。
