# Preflight Checklist

在执行任何会改变 repo、Cloudflare、GitHub 或 DNS 的动作前，先完成这些检查。

## 本地项目

```bash
pwd
git status --short --branch
git remote -v
git branch --show-current
rg --files -g '!*node_modules*' -g '!*.png' -g '!*.jpg' -g '!*.jpeg' -g '!*.gif' -g '!*.webp' | sed -n '1,180p'
```

检查包管理器：

```bash
test -f pnpm-lock.yaml && echo pnpm
test -f yarn.lock && echo yarn
test -f package-lock.json && echo npm
test -f bun.lockb -o -f bun.lock && echo bun
```

优先使用仓库已有包管理器。JS/TS 项目默认优先 `pnpm`，除非项目已有其它 lockfile。

## Cloudflare 线索

```bash
rg -n 'wrangler|cloudflare|open-next|opennext|workers|pages|d1|r2|kv_namespaces|queues|vectorize' package.json wrangler.* open-next.config.* 2>/dev/null || true
```

如果已经有 `wrangler.jsonc` 或 `wrangler.toml`，不要假设它正确。后续由 `jz-create-cf-site` 或 `jz-push-code` 复查。

## GitHub Actions

```bash
rg --files .github/workflows 2>/dev/null || true
rg -n 'wrangler|cloudflare|pages|deploy|issues|issue_comment|workflow_dispatch|auto-pr' .github/workflows 2>/dev/null || true
```

只记录是否已有生产部署 workflow 和 Auto PR workflow。缺失时不要在本 skill 里直接补，由对应阶段处理。

## 域名和统计

```bash
rg -n 'sitemap|robots|canonical|NEXT_PUBLIC_SITE_URL|PUBLIC_SITE_URL|SITE_URL|UMAMI|CLARITY|SENTRY|INDEXNOW' . 2>/dev/null || true
```

如果没有正式域名，`jz-setup-analytics` 不能进入完成态。

## Secret 安全检查

只检查变量名和文件状态，不输出值：

```bash
for f in .env .env.local .env.production .env.development .dev.vars .env.example; do
  test -f "$f" && awk -F= -v file="$f" '/^[A-Za-z_][A-Za-z0-9_]*=/{print file ":" $1}' "$f"
done
for f in .env .env.local .env.production .env.development .dev.vars; do
  test -f "$f" && git check-ignore -q "$f" && echo "$f ignored" || true
done
for f in .env .env.local .env.production .env.development .dev.vars; do
  test -f "$f" && git ls-files --error-unmatch "$f" >/dev/null 2>&1 && echo "$f tracked" || true
done
```

如果 secret 文件已被 Git 跟踪，先停止相关阶段，按对应 skill 的安全规则处理。
