---
name: jz-manage-cron-jobs
description: 管理 cron-job.org 定时任务。需要检查 API key、列出 job/folder、查看详情和历史、创建/更新/启停/删除定时任务，或把 HTTP API 加到外部调度时使用。
---

# cron-job.org 管理

用于通过 cron-job.org REST API 管理外部 HTTP 定时任务。

官方 API 支持创建、更新、删除和查看 cron job。创建 job 使用 `PUT /jobs`，更新使用 `PATCH /jobs/<jobId>`，删除使用 `DELETE /jobs/<jobId>`。API key 等同账号密码，不要输出、提交或写进任务正文。

## 配置

默认读取：

```text
~/.config/skills/jz-manage-cron-jobs/.env
```

也可用 `JZ_CRON_JOB_ENV` 指向其它 `.env` 文件。

需要的变量：

```bash
CRON_JOB_API_KEY=<secret>
```

可选变量：

```bash
CRON_JOB_API_BASE=https://api.cron-job.org
```

## 常用命令

在 skill 目录内运行：

```bash
./scripts/cron_job.mjs check
./scripts/cron_job.mjs list
./scripts/cron_job.mjs get <jobId>
./scripts/cron_job.mjs history <jobId>
```

创建一个每小时执行一次的 GET 任务：

```bash
./scripts/cron_job.mjs create \
  --title "Health check" \
  --url "https://example.com/api/health" \
  --enabled true \
  --every-hour
```

创建一个每天 03:15 执行的 POST 任务：

```bash
./scripts/cron_job.mjs create \
  --title "Daily billing task" \
  --url "https://example.com/api/admin/billing" \
  --method POST \
  --header "x-cron-secret:<secret>" \
  --body '{"source":"cron"}' \
  --daily-at 03:15 \
  --timezone UTC \
  --enabled true
```

启停和修改：

```bash
./scripts/cron_job.mjs enable <jobId>
./scripts/cron_job.mjs disable <jobId>
./scripts/cron_job.mjs update <jobId> --title "New title"
./scripts/cron_job.mjs delete <jobId>
```

文件夹：

```bash
./scripts/cron_job.mjs folders
./scripts/cron_job.mjs folder-create "Production"
./scripts/cron_job.mjs folder-update <folderId> "Production jobs"
./scripts/cron_job.mjs folder-delete <folderId>
```

## 调度参数

脚本支持三种常用写法：

- `--every-hour`：每小时 0 分执行。
- `--every-minute`：每分钟执行。慎用，容易打到 API 和目标站。
- `--daily-at HH:MM`：每天指定时间执行。

如果需要完整 cron-job.org schedule，可传 JSON：

```bash
./scripts/cron_job.mjs create \
  --title "Quarter hourly" \
  --url "https://example.com/api/task" \
  --schedule-json '{"timezone":"UTC","expiresAt":0,"hours":[-1],"mdays":[-1],"minutes":[0,15,30,45],"months":[-1],"wdays":[-1]}'
```

schedule 字段规则：

- `hours`: `0-23`，`[-1]` 表示每小时。
- `minutes`: `0-59`，`[-1]` 表示每分钟。
- `mdays`: `1-31`，`[-1]` 表示每天。
- `months`: `1-12`，`[-1]` 表示每月。
- `wdays`: `0-6`，`0` 是周日，`[-1]` 表示每天。
- `expiresAt`: `YYYYMMDDhhmmss`，`0` 表示不过期。

## 输出和安全

脚本输出会隐藏：

- API key。
- URL query。
- `authorization`、`cookie`、`x-cron-secret` 等敏感 header。
- job body 和 history body。

创建、更新、删除前确认目标 URL、jobId、method 和 schedule。生产任务建议先 `--enabled false` 创建，再检查详情，最后 `enable <jobId>`。

## API 限制

cron-job.org 默认每日 API 调用额度是 100 次。列表、详情、历史接口通常是 5 req/s；创建 job 是 1 req/s 且 5 req/min。不要用循环批量创建任务。
