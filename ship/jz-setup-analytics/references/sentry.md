# Sentry

创建 Sentry 项目、获取 DSN 并配置到部署环境时读取。

Sentry error tracking 是 project-scoped。每个部署需要独立的 Sentry 项目以隔离 issue。项目 slug 使用当前 repo 根目录名（`pnpm exec wrangler` 的 `name`、`package.json` 的 `name`、或当前目录名）。

## 来源顺序

1. 从凭据文件读取 `SENTRY_API_TOKEN`（仅在 `~/.config/skills/jz-setup-analytics/.env` 或 skill 根目录 `.env`）。
2. 如果 token 缺失，报告 Sentry 为 `skipped`，reason 为 `no SENTRY_API_TOKEN`。
3. 不要在 repo dotenv（`.env`、`.env.local`）中查找 Sentry API token——repo dotenv 只放 DSN。
4. 不要交互式索要 token。

## API 操作

### Token 要求

需要 auth token（不是 DSN）。Token 需具备以下权限：
- `project:read`
- `project:write`
- `project:admin`
- `org:read`

Token 创建地址：[Sentry Auth Tokens](https://localfirstllc.sentry.io/settings/auth-tokens/)

### 检测 org 和 team slug

如果 `SENTRY_ORG_SLUG` 或 `SENTRY_TEAM_SLUG` 未设置，通过 list projects 自动检测：

```bash
curl -s -H "Authorization: Bearer $SENTRY_API_TOKEN" \
  "https://sentry.io/api/0/projects/" \
  | python3 -c "
import sys, json
projects = json.load(sys.stdin)
if projects:
    org = projects[0]['organization']
    team = projects[0]['teams'][0] if projects[0].get('teams') else None
    print(f'org_slug={org[\"slug\"]}')
    print(f'org_name={org[\"name\"]}')
    if team:
        print(f'team_slug={team[\"slug\"]}')
        print(f'team_name={team[\"name\"]}')
"
```

未设置时默认使用 `localfirstllc`。

### 检查项目是否存在

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $SENTRY_API_TOKEN" \
  "https://sentry.io/api/0/projects/$SENTRY_ORG_SLUG/$PROJECT_SLUG/"
```

HTTP 200 = 已存在；HTTP 404 = 不存在。

### 新建项目

```bash
curl -s -w "\n%{http_code}" \
  -H "Authorization: Bearer $SENTRY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$PROJECT_NAME\",\"slug\":\"$PROJECT_SLUG\",\"platform\":\"javascript\"}" \
  "https://sentry.io/api/0/teams/$SENTRY_ORG_SLUG/$SENTRY_TEAM_SLUG/projects/"
```

- `PROJECT_SLUG`：当前 repo 根目录名（小写、不含空格）
- `PROJECT_NAME`：可读名称，通常与 slug 相同
- `platform`：`javascript` 适用于 Next.js、Astro、Cloudflare Workers 等。Python/FastAPI 项目用 `python-fastapi`。

HTTP 201 = 创建成功。HTTP 409 = 项目 slug 已存在（改用已有项目即可）。

### 获取 DSN

```bash
curl -s -H "Authorization: Bearer $SENTRY_API_TOKEN" \
  "https://sentry.io/api/0/projects/$SENTRY_ORG_SLUG/$PROJECT_SLUG/keys/" \
  | python3 -c "
import sys, json
keys = json.load(sys.stdin)
for k in keys:
    print(f'DSN={k[\"dsn\"][\"public\"]}')
    print(f'project_id={k[\"projectId\"]}')
    print(f'name={k[\"name\"]}')
"
```

DSN 格式：`https://<key>@o<org_id>.ingest.us.sentry.io/<project_id>`

## 写入 DSN

DSN 是 secret，不属于公开前端。写入位置取决于项目运行环境：

### Cloudflare Workers

```bash
echo "<DSN>" | pnpm exec wrangler secret put SENTRY_DSN
```

Worker 代码中从 `env.SENTRY_DSN` 读取。Wrangler 配置中不需要额外声明（secret 自动可用）。如需在 `env.d.ts` 中声明类型：

```ts
SENTRY_DSN?: string;
```

### Vercel / Vercel-style 部署

```bash
# 生产环境
vercel env add SENTRY_DSN production
# 或通过 Vercel dashboard → Settings → Environment Variables
```

Vercel 中不要使用 `NEXT_PUBLIC_SENTRY_DSN`——Sentry DSN 是服务端 secret（尽管 DSN 本身不包含 API key，但暴露 DSN 会允许任意客户端发送事件）。如果项目需要客户端错误追踪，单独建一个 client-side 项目并使用 `NEXT_PUBLIC_` 前缀。

### 本地 `.env`

如果确认 `.env` 在 `.gitignore` 中：

```bash
echo "SENTRY_DSN=<DSN>" >> .env
```

## 已有项目复用

如果项目已存在：
- 复用已有项目，不新建
- 获取其 DSN
- 检查是否已有事件流入（`firstEvent` 字段）

## 最小目标

- Sentry 项目存在且 slug 匹配当前 repo 根目录名
- DSN 已获取
- DSN 已写入对应运行环境的 secret / environment variable
- 如有 repo 编辑权限，Sentry 初始化代码已正确读取 DSN（从 `env.SENTRY_DSN` 或对应来源）

## 安全

- 绝不在输出中打印 `SENTRY_API_TOKEN`
- 绝不在日志或最终摘要中打印完整 DSN（可以打印 `<10 chars>...<last 4>` 格式的简写）
- 绝不把 DSN 写入前端 public env（`NEXT_PUBLIC_*`、`VITE_*`、`PUBLIC_*` 等），除非用户明确要求客户端错误追踪
- 仓库 `.gitignore` 必须包含 `.env`，确保 DSN 不会提交到版本控制
