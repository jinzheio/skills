# Spaceship Registrar — 修改 Nameserver

当域名 registrar 是 Spaceship 时，使用 Spaceship API 修改 nameserver。

## 认证

API key 存放在 `~/.config/skills/jz-launch-domain/.env`：

```
SPACESHIP_API_KEY=...
SPACESHIP_API_SECRET=...
```

- **Base URL**: `https://spaceship.dev/api/v1`
- **认证方式**：通过 custom headers `x-api-key` 和 `x-api-secret`

所有请求必须带这两个 header：

```bash
source ~/.config/skills/jz-launch-domain/.env

-H "x-api-key: ${SPACESHIP_API_KEY}"
-H "x-api-secret: ${SPACESHIP_API_SECRET}"
```

## 操作流程

### 1. 获取当前域名信息

```bash
source ~/.config/skills/jz-launch-domain/.env
DOMAIN="example.com"

curl -sS \
  -H "x-api-key: ${SPACESHIP_API_KEY}" \
  -H "x-api-secret: ${SPACESHIP_API_SECRET}" \
  "https://spaceship.dev/api/v1/domains/${DOMAIN}" | python3 -m json.tool
```

返回结果中包含 `nameservers` 字段。`provider` 为 `"basic"` 表示使用 Spaceship 默认 NS，`"custom"` 表示已改为第三方 NS。

### 2. 修改 Nameserver

使用 `PUT`，body 为扁平 JSON（`provider` + `hosts` 数组）：

```bash
source ~/.config/skills/jz-launch-domain/.env
DOMAIN="example.com"

curl -sS -X PUT \
  -H "x-api-key: ${SPACESHIP_API_KEY}" \
  -H "x-api-secret: ${SPACESHIP_API_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"provider":"custom","hosts":["elle.ns.cloudflare.com","igor.ns.cloudflare.com"]}' \
  "https://spaceship.dev/api/v1/domains/${DOMAIN}/nameservers"
```

成功时返回更新后的 nameserver 信息：

```json
{
  "provider": "custom",
  "hosts": ["elle.ns.cloudflare.com", "igor.ns.cloudflare.com"]
}
```

**注意**：NS 列表必须替换为 Cloudflare 分配给该 zone 的实际 nameserver（每个 zone 可能不同，从 Cloudflare zone 面板获取）。

### 3. 验证 NS 变更

**注册商侧**（最快，立即反映）：

```bash
source ~/.config/skills/jz-launch-domain/.env

curl -sS \
  -H "x-api-key: ${SPACESHIP_API_KEY}" \
  -H "x-api-secret: ${SPACESHIP_API_SECRET}" \
  "https://spaceship.dev/api/v1/domains/${DOMAIN}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['nameservers'])"
```

**Registry 侧**（`.com` 注册局，通常几分钟内生效）：

```bash
dig NS DOMAIN_NAME @a.gtld-servers.net +short
```

**Cloudflare zone**（NS 变更后 zone 状态从 `pending` 变为 `active`）：

```bash
curl -sS "https://api.cloudflare.com/client/v4/zones/ZONE_ID" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['result']['status'])"
```

## 其他操作

### 列出所有域名

```bash
source ~/.config/skills/jz-launch-domain/.env

curl -sS \
  -H "x-api-key: ${SPACESHIP_API_KEY}" \
  -H "x-api-secret: ${SPACESHIP_API_SECRET}" \
  "https://spaceship.dev/api/v1/domains?take=50&skip=0" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(f'{i[\"name\"]}  ns={i[\"nameservers\"][\"provider\"]}') for i in d.get('items',[])]"
```

### 搜索特定域名

添加 `&search=keyword` 参数即可。
