---
name: jz-audit-neon-usage
description: 分析 Neon 数据库请求、连接和无法休眠的原因。适用于 Next.js、Vercel、Cloudflare Workers、后台 runner、cron、ISR、auth session、webhook 等会触发数据库访问的项目。默认只读，先用平台日志定位请求路径，再结合代码和数据库统计判断来源。
---

# Neon Usage Audit

## 目标

找出 Neon 数据库请求来自哪里，尤其是：

- 数据库无法 scale to zero。
- Neon requests / compute active time 比预期高。
- 静态页面仍然触发数据库访问。
- runner、cron-job.org、webhook、auth、ISR 或后台任务持续打数据库。
- 需要判断是 read、write、连接建立、缓存失效还是平台重试导致的访问。

默认只做只读诊断。不要修改代码、部署配置、数据库数据或云平台设置，除非用户明确要求修复。

## 先问清楚

如果用户没有给出足够信息，先确认：

- 项目托管平台：Vercel、Cloudflare Workers、Render、Railway、自托管等。
- 时间窗口：例如最近 2 小时、6 小时、24 小时。
- 用户看到的异常：Neon requests、active compute、connection count、账单、日志告警等。
- 是否允许读取本地 `.env`、平台配置、数据库 URL 和日志。
- 是否使用 cron-job.org 或其它外部 cron 服务；如果使用 cron-job.org，是否允许读取本机未跟踪配置里的 `CRON_JOB_API_KEY`。

如果当前环境已经在目标项目根目录，优先自动读取项目配置，不要让用户重复提供。

## 调查顺序

1. **确认数据源**
   - 读取项目的 package scripts、托管平台配置、cron 配置、API 路由、middleware/proxy、ORM 初始化代码。
   - 找到数据库入口，例如 `DATABASE_URL`、Neon serverless driver、Prisma、Drizzle、Kysely、pg Pool。
   - 标记所有会触发 DB 的路径：页面渲染、API routes、server actions、auth、webhook、cron、runner、ISR revalidation。

2. **查外部 cron**
   - 如果项目使用 cron-job.org，先读取本机未跟踪配置中的 `CRON_JOB_API_KEY`，再按 `references/cron-job-org.md` 列出 cron jobs。
   - 将 job URL 归一化为 host + path，不输出 secret query、token、完整认证 header 或响应体。
   - 标记会打到当前项目的 API path，例如 `/api/admin/*`、`/api/billing/*`、`/api/deploy/*`、`/api/install/*`、`/api/auth/*`。
   - 对每个相关 job 记录：title、enabled、method、schedule、last/next execution、last status、对应 handler 是否访问 DB。
   - 如果 cron 服务不可用或 API key 缺失，说明缺口，不要跳过代码里的 cron handler 排查。

3. **拉平台请求日志**
   - 按时间窗口聚合 request path、status、cache/source、method。
   - 去重 request id，避免 CLI 分页或重复输出造成误判。
   - 把路径归一化，例如 `/api/deploy/<sid>/runner/auth/verify` 归成 `/api/deploy/{sid}/runner/auth/verify`。
   - 分出静态命中、serverless 执行、edge/proxy、404 扫描、认证回调、后台任务。

4. **查 Neon / Postgres 侧证据**
   - 如果启用了 `pg_stat_statements`，按 calls 排序看 SQL 指纹。
   - 如果没有启用，使用 `pg_stat_database`、`pg_stat_user_tables`、业务表时间戳和最近写入记录做旁证。
   - 不要把 Postgres 累计表统计当作“过去几小时”的精确数据，除非知道 stats reset 时间。

5. **结合代码确认**
   - 对平台日志中的高频 path，打开对应 handler。
   - 找到是否调用 DB、auth session、cache revalidation、runner token 校验、job claim/ack、webhook handler。
   - 判断访问是必要行为、兼容旧路径、错误重试、爬虫扫描，还是可以缓存/降频。

6. **给出结论和改法**
   - 先列最可能来源，按证据强度排序。
   - 每条来源写清：触发场景、对应路径、对应代码、是否会唤醒 Neon、能否减少。
   - 区分“已证实”“推断”“需要更多日志”。

## 常见来源

- 首页或 landing page 的 server component 读取 DB。
- ISR 页面在 `revalidate` 到期后重新渲染，触发 DB。
- `unstable_cache` 设置了短 TTL，页面命中缓存但数据缓存到期。
- header / nav 为了显示头像或 dashboard 调 auth session。
- 浏览器端根据 localStorage auth hint 自动请求 `/api/profile`、`/api/billing/status`、`/api/deploy/latest`。
- better-auth / NextAuth session 读取或更新 session 表。
- webhook、cron、release check、runner health check。
- cron-job.org 定时请求后台 API，例如 release check、runner health、billing grace/period-end。
- 部署 runner 定期 `auth/verify`、`jobs/claim`、`ack` 或 config sync。
- 平台重试、bot 扫描 `.env`、`wp-login.php` 等 404 路径。404 本身未必打 DB，要看是否进入 serverless/proxy。

## cron-job.org

cron-job.org 查询流程见 `references/cron-job-org.md`。使用时必须：

- 只做 `GET /jobs`、必要时做 `GET /jobs/<jobId>/history`；不要创建、更新、删除 cron job。
- 从本机未跟踪配置读取 `CRON_JOB_API_KEY`。不要把 key 写入仓库、报告或命令输出。
- skill 本机配置统一放在 `~/.config/skills/jz-audit-neon-usage/.env` 或 `~/.config/skills/jz-audit-neon-usage/config.yml`。
- 按 host + path 匹配当前项目，不用完整 URL 中的 query 做报告。
- 将 cron job 与代码 handler 对上：只要 handler import `db`、调用 auth session、调用 billing/cache/runner helper，就标记为会触发 Neon。
- 把 cron 触发时间和 Neon/Postgres 最近写入时间交叉比较；时间接近只能作为旁证，不能单独当作确定归因。

## Vercel

Vercel 查询流程见 `references/vercel.md`。使用时必须：

- 加 `--environment production` 或明确目标环境。
- 加 `--no-follow`，避免命令一直挂着。
- 加 `--no-branch`，避免当前本地分支过滤掉线上 `main` 日志。
- 用 JSON 输出后按 `id` 去重。

## Neon / Postgres 查询

优先使用只读 SQL。不要输出连接串、用户名、密码、token。

可用查询：

```sql
select now() as db_now;

select extname
from pg_extension
order by 1;

select stats_reset
from pg_stat_database
where datname = current_database();

select datname,
  xact_commit,
  xact_rollback,
  tup_returned,
  tup_fetched,
  tup_inserted,
  tup_updated,
  tup_deleted
from pg_stat_database
where datname = current_database();

select schemaname,
  relname,
  n_tup_ins,
  n_tup_upd,
  n_tup_del,
  n_live_tup
from pg_stat_user_tables
order by relname;
```

如果 `pg_stat_statements` 存在：

```sql
select calls,
  round(total_exec_time::numeric, 2) as total_ms,
  rows,
  left(regexp_replace(query, '\s+', ' ', 'g'), 220) as query
from pg_stat_statements
order by calls desc
limit 30;
```

如果没有 `pg_stat_statements`，说明无法从数据库侧直接按 SQL 指纹归因。改用平台日志、代码路径和业务表最近写入时间交叉判断。

## 输出格式

```text
结论：
- 主要来源：...
- 次要来源：...
- 不是主要来源：...

证据：
- cron-job.org：...
- 平台日志：...
- Neon/Postgres：...
- 代码路径：...

建议：
1. ...
2. ...
3. ...

残余不确定：
- ...
```

## 安全规则

- 不输出数据库连接串、平台 token、cookie、session、私钥。
- 不在 public repo 文档里写本机绝对路径、真实项目私有路径、真实账号或私有域名。
- 只读调查时，不执行迁移、写 SQL、部署、重启服务。
- 如需修复，先说明改动会影响的请求路径和验证方式。
