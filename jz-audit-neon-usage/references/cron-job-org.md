# cron-job.org 查询

用于判断外部 cron 是否会定时打到当前项目 API，并进一步触发 Neon。

## 凭证

优先从本机未跟踪配置读取：

```bash
set -a
source "$HOME/.config/jzskills/jz-audit-neon-usage/.env"
set +a
```

skill 配置目录统一使用 `~/.config/jzskills/<skill-name>/`。本 skill 的 `.env` 只需要：

```bash
CRON_JOB_API_KEY=<secret>
```

如果当前项目 `.env` 里已经有 `CRON_JOB_API_KEY`，可以把该变量复制到上述本机配置。不要把 key 写进仓库。

## 官方 API

官方文档：https://docs.cron-job.org/rest-api.html

关键信息：

- Endpoint: `https://api.cron-job.org/`
- Auth: `Authorization: Bearer <api-key>`
- List jobs: `GET /jobs`
- Job details: `GET /jobs/<jobId>`
- History: `GET /jobs/<jobId>/history`
- 默认 daily limit 是 100 requests/day；列表接口限速是 5 requests/second。

## 只读查询

```bash
curl -sS \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CRON_JOB_API_KEY" \
  https://api.cron-job.org/jobs
```

只输出归一化结果：

- `jobId`
- `title`
- `enabled`
- host + path
- request method
- last status
- last execution
- next execution
- schedule

不要输出：

- API key
- 完整认证 header
- secret query 参数
- saved response body

## 归因方法

1. 用 host 和 path 找当前项目相关 job，例如：
   - `/api/admin/*`
   - `/api/billing/*`
   - `/api/deploy/*`
   - `/api/install/*`
   - `/api/auth/*`
2. 打开对应 route handler。
3. 标记是否会触发 DB：
   - 直接 import `db`
   - 调用 `auth.api.getSession`
   - 调用 billing subscription/cache helper
   - enqueue/claim/ack runner job
   - 更新 release check fingerprint
4. 把 cron 的 last/next execution 与 Postgres 侧最近写入时间对齐。

时间接近只能作为旁证。最终结论要同时引用 cron job、handler 代码和数据库侧证据。

## 输出示例

```text
cron-job.org：
- OpenClaw version check：enabled，POST /api/admin/openclaw-release-check，每 2 小时一次。handler 会读写 install_sessions 和 deployment_agent_jobs，会唤醒 Neon。
- Runner Health：enabled，POST /api/admin/runner-health，每 6 小时一次。handler 会查询部署状态，会唤醒 Neon。
```
