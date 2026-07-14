# Vercel 日志查询

用于把 Vercel 请求日志和 Neon 数据库访问关联起来。目标是找出哪些 path 进入了 serverless / middleware，并判断这些 path 是否会访问 DB。

## 前置条件

- Vercel CLI 已登录，并且当前项目已关联 Vercel project。
- 如果项目未关联，先用用户提供的 project/team 信息，或让用户在目标项目中执行 Vercel link。
- 查询生产问题时明确使用 production 环境。

## 基础命令

```bash
vercel logs --environment production --since 6h --limit 1000 --json --no-branch --no-follow
```

参数含义：

- `--environment production`：只看生产环境。
- `--since 6h`：时间窗口，可换成 `2h`、`24h` 或 ISO 时间。
- `--limit 1000`：取更多日志。
- `--json`：方便聚合。
- `--no-branch`：不按当前本地 Git 分支过滤。
- `--no-follow`：只取历史日志，不持续监听。

## 去重聚合

Vercel CLI 输出可能出现重复行。按 `id` 去重后再统计。

```bash
vercel logs --environment production --since 6h --limit 1000 --json --no-branch --no-follow 2>/dev/null \
  | jq -r 'select(.requestPath) | [.id,.requestPath,.source,(.responseStatusCode|tostring),(.cache//""),.requestMethod] | @tsv' \
  | sort -u -k1,1 \
  | awk -F'\t' '{
      path=$2;
      sub(/\?.*/, "", path);
      if (path ~ /^\/api\/deploy\/[A-Za-z0-9_-]+\/runner\/auth\/verify$/) path="/api/deploy/{sid}/runner/auth/verify";
      if (path ~ /^\/api\/deploy\/[A-Za-z0-9_-]+\/skills\/auth\/verify$/) path="/api/deploy/{sid}/skills/auth/verify";
      if (path ~ /^\/api\/deploy\/[A-Za-z0-9_-]+\/runner\/jobs\/claim$/) path="/api/deploy/{sid}/runner/jobs/claim";
      if (path ~ /^\/api\/deploy\/[A-Za-z0-9_-]+\/runner\/jobs\/[^\/]+\/ack$/) path="/api/deploy/{sid}/runner/jobs/{jobId}/ack";
      c[path]++;
    }
    END { for (p in c) print c[p] "\t" p }' \
  | sort -nr \
  | head -80
```

## API 路径明细

```bash
vercel logs --environment production --since 6h --limit 1000 --json --no-branch --no-follow 2>/dev/null \
  | jq -r 'select(.requestPath | startswith("/api/")) | [.id,.requestPath,.source,(.responseStatusCode|tostring),(.cache//""),.timestamp] | @tsv' \
  | sort -u -k1,1 \
  | sort -k6,6n
```

## 看 cache/source 分布

```bash
vercel logs --environment production --since 6h --limit 1000 --json --no-branch --no-follow 2>/dev/null \
  | jq -r 'select(.requestPath) | [.id,.source,(.cache//""),(.responseStatusCode|tostring)] | @tsv' \
  | sort -u -k1,1 \
  | cut -f2- \
  | sort \
  | uniq -c \
  | sort -nr
```

判断方式：

- `static HIT`：通常不会触发 DB。
- `serverless` / `serverless-middleware` + `MISS` / `BYPASS`：需要打开对应 route handler 看是否访问 DB。
- `REVALIDATED`：ISR 重新渲染，可能触发 DB。
- `404`：不一定访问 DB。要看该 404 是否进入 serverless，以及项目的 not-found / proxy 是否读 DB。

## 常见归因

- `/api/auth/*`：auth session、callback、magic link、OAuth，通常会读写 auth 表。
- `/api/billing/status`：用户状态、订阅、seat availability，通常会读 DB，也可能访问 Stripe。
- `/api/deploy/latest`、`/api/deploy/list`：用户部署状态，通常会读 DB。
- `/api/deploy/{sid}/runner/auth/verify`：runner 或 notify worker 验证机器 token，通常会读 DB。
- `/api/deploy/{sid}/runner/jobs/claim`：runner 拉取待执行任务，通常会读写 DB。
- `/api/deploy/{sid}/runner/jobs/{jobId}/ack`：runner 上报任务结果，通常会写 DB。
- 页面 path 的 `REVALIDATED`：检查 page server component、`generateMetadata`、`unstable_cache`、`fetch` 和 ORM 调用。

## 报告时要写清

- 查询时间窗口。
- 是否按 request id 去重。
- Top path 和 API path 分布。
- 哪些 path 已经和代码中的 DB 调用对应上。
- 哪些只是推断，需要更多平台日志或 Neon SQL 指纹确认。
