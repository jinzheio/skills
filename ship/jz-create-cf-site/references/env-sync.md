# Cloudflare Env Sync

## 目标

只同步生产运行所需的最小环境变量和 secret。不要复制开发、测试、日志、旧平台或临时变量。

## 发现变量

只输出变量名和来源文件，不输出值：

```bash
for f in .env .env.local .env.production .env.development .dev.vars .env.example; do
  test -f "$f" && awk -F= -v file="$f" '/^[A-Za-z_][A-Za-z0-9_]*=/{print file ":" $1}' "$f"
done
```

检查 env 文件是否安全：

```bash
for f in .env .env.local .env.production .env.development .dev.vars; do
  test -f "$f" && git check-ignore -q "$f" && echo "$f ignored" || true
done
for f in .env .env.local .env.production .env.development .dev.vars; do
  test -f "$f" && git ls-files --error-unmatch "$f" >/dev/null 2>&1 && echo "$f tracked" || true
done
```

如果 `.env.local` 未被忽略，先补 `.gitignore`。如果已纳入 Git 管理，先让用户确认是否从索引移除。

## 分类

写入 `wrangler.jsonc` 的 `vars`：

- public base URL
- feature flags
- non-secret numeric/string config

写入 Cloudflare secrets：

- API keys
- OAuth client secret
- database password
- webhook secret
- token
- private signing key

不要把 secret 写入 `wrangler.jsonc`、GitHub Actions YAML、README 或提交记录。

## Wrangler secret

交互式写入：

```bash
<pm> exec wrangler secret put <NAME>
```

验证 secret 名称，不读取值：

```bash
<pm> exec wrangler secret list
```

## Workers Builds

如果使用 Workers Builds：

- runtime secret 放 Cloudflare Worker secrets。
- build-time env 放 Workers Builds 环境变量。
- `WORKERS_CI=1` 可用于区分 Cloudflare build 环境。

如果 CLI/API 不能设置某项，汇报为 `manual`，并列出变量名，不列出变量值。

如果用户使用 Wrangler 直发，不需要 Workers Builds 环境变量。只同步 Worker runtime secrets 和 Wrangler 配置里的非 secret `vars`。

## 本机 Cloudflare 凭据

当前项目可使用 `.env.local` 保存：

```text
CLOUDFLARE_API_TOKEN=...
CLOUDFLARE_ACCOUNT_ID=...
```

这里保存的是项目自己的最小权限 token。`create-cf-token` 本地配置指定的共享 token 只用于创建项目 token，或给已有项目 token 增加必要权限。不要用共享 token 执行项目 deploy、创建资源、写 GitHub Secrets 或作为 Workers Builds 凭据。

用 `scripts/with-cloudflare-env.mjs` 注入 Wrangler：

```bash
node <skill-dir>/scripts/with-cloudflare-env.mjs <pm> exec wrangler whoami
```

这个脚本只读取 `CLOUDFLARE_API_TOKEN` 和 `CLOUDFLARE_ACCOUNT_ID`，不输出值。
