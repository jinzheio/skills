# Cloudflare Deploy Verify

## 完成条件

不要只看 deploy command 退出码。至少验证：

- build/check 通过，或明确说明跳过原因。
- Cloudflare 返回 Worker / deployment 信息。
- 生产 URL HTTPS 可达。
- HTML title 或核心内容符合目标站点。
- 静态资源返回 200。
- API / health endpoint 可用，如果项目有 API。
- D1/R2/Queues/Vectorize 等 bindings 可访问，如果项目使用。

## 基础验证

```bash
curl -sSIL --max-time 20 https://<worker>.<subdomain>.workers.dev
curl -sSL --max-time 20 https://<worker>.<subdomain>.workers.dev | rg -o '<title>[^<]+'
curl -sSIL --max-time 20 https://<worker>.<subdomain>.workers.dev/favicon.ico
```

如果已有临时 preview URL 或自定义域名，对目标 URL 重复同样检查。

## API 验证

```bash
curl -sS --max-time 20 https://<url>/api/health
```

如果没有 health endpoint，选择一个只读、无副作用的 API。

## Workers 信息

```bash
<pm> exec wrangler deployments list
<pm> exec wrangler versions list
```

如果命令不可用或权限不足，说明原因，不阻塞已可访问的生产验证。

## D1 验证

```bash
<pm> exec wrangler d1 execute <db-name> --remote --command "select name from sqlite_master where type='table' order by name;"
```

## R2 验证

```bash
<pm> exec wrangler r2 bucket list
```

如果要验证对象读取，只访问无敏感内容的测试对象。

## 常见失败

- `workers.dev` 不可达：确认账户是否禁用了 workers.dev，或部署是否只绑定 custom domain。
- `No such module`：Worker bundle 入口或 adapter build 产物不匹配。
- `Missing entry-point to Worker script or to assets directory`：`main` 或 `assets.directory` 配置错误。
- Next.js runtime 报 Node API：确认 `compatibility_flags` 包含 `nodejs_compat`，并检查依赖是否需要 Workers 不支持的 Node 能力。
- 静态路由刷新 404：SPA 需要 `assets.not_found_handling = "single-page-application"`。
- API 路由被静态 assets 截获：为 API path 配置合理的 assets routing，或改 Worker route 处理顺序。

## 汇报格式

每项使用 `docs/status-terms.md` 状态词：

```text
- GitHub repo: done — <url>
- Cloudflare deploy: done — <url>, deployment <id>
- Publish mode: done — Wrangler 直发
- Env/secrets: partial — 已同步 3 个 secret，STRIPE_WEBHOOK_SECRET 缺失
- HTTP verification: done — 200, title matched
```
