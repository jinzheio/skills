# Pages Direct Upload Functions 运行时变量

适用于 `wrangler pages deploy <dist>` 直接上传 Cloudflare Pages，且项目包含 Pages Functions。

## 部署形态检查

```bash
rg -n '"deploy"|pages deploy|opennextjs-cloudflare|wrangler deploy' package.json
test -f wrangler.toml && sed -n '1,80p' wrangler.toml
test -f wrangler.jsonc && sed -n '1,80p' wrangler.jsonc
rg --files | rg '^(functions/|open-next\.config\.(ts|js|mjs)|src/app/api/)'
```

仅在同时满足这些条件时，才考虑临时 `[vars]` 部署桥接：

- 部署命令是 `wrangler pages deploy <dist>` 或等价 Direct Upload。
- 项目包含 Pages Functions，例如 `functions/api/*`、`_middleware.ts`。
- 服务端代码从 `context.env` 读取运行时变量。
- 真实 API route 证明 `context.env` 读不到 Cloudflare Dashboard/API 已配置变量。

不要把这个方案用于 OpenNext/Worker 项目。识别信号：

- `opennextjs-cloudflare deploy` 或 `wrangler deploy`。
- `wrangler` 配置有 Worker `main`，例如 `.open-next/worker.js`。
- 服务端代码通过 `process.env` 或 Worker bindings 读变量。

## 处理规则

- `VITE_*` / `NEXT_PUBLIC_*` 是前端公开变量，可能进入客户端 bundle，不要放 Stripe、邮件、数据库、Webhook、服务端 API key。
- Pages Functions 的服务端变量通过 `context.env` 读取；不要在 Functions 中依赖 `process.env`。
- Direct Upload 中，Dashboard/API 里能看到 env/secrets，不等于当前部署的 Functions 一定能读到；不要表述成“Functions 实际走 preview env”。
- 如果需要临时 `[vars]` 桥接，必须由脚本完成：备份 `wrangler.toml`、追加 `[vars]`、执行 `wrangler pages deploy`、退出时还原文件；脚本日志只输出变量名和类型，不输出值。
- 部署完成后，把 Cloudflare 项目配置恢复为 `secret_text`；不要提交含密钥的 `wrangler.toml`。

## 部署后复查

```bash
# 公开产物不得包含服务端密钥或服务端变量名
curl -sS https://example.com/assets/<bundle>.js | rg 'sk_live|sk_test|whsec_|TOKEN|SECRET|PASSWORD' || true
curl -sS https://example.com/ | rg 'sk_live|sk_test|whsec_|TOKEN|SECRET|PASSWORD' || true

# 真实 API route 必须能读到 runtime vars，但响应不得回显密钥
curl -sS -i https://example.com/api/<runtime-dependent-route>
```

成功标准：

- `wrangler.toml` 还原到不含密钥。
- `.env` / `.env.local` 被 Git 忽略且未纳入 Git 管理。
- 线上前端 bundle 和 HTML 没有服务端密钥值。
- 线上 API 能正常使用服务端变量。
- Cloudflare 项目配置中服务端变量为 `secret_text`；公开前端变量才允许是 `plain_text`。
