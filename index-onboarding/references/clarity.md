# Microsoft Clarity

验证或接入 Clarity 状态时读取。

Clarity 是 project-scoped。优先使用 `SITE_INTEGRATIONS_CONFIG` 配置的共享 integration map。若 map 缺失或没有目标域名的 Clarity 配置，从当前环境和已解析 repo 的 `.env` / `.env.local` 读取 `CLARITY_ID` 和 `CLARITY_TOKEN`。

Microsoft Clarity MCP server 和 Data Export API 需要已有 Clarity project 和 project-level Data Export API token。把它们当作 analytics read/query 工具，不当作 project creation API。

## 来源顺序

1. 在 integration map 中解析目标域名。
2. 读取 `domains[hostname].clarity`。
3. 如果存在 `clarity.project_id` 和 `clarity.token`，使用它们。
4. 如果 map 缺失、不可读、无效或没有目标域名 Clarity 配置，从当前进程环境读取 `CLARITY_ID` 和 `CLARITY_TOKEN`。
5. 如果当前环境缺任一值且 repo 已解析，检查 repo 内 `.env` 和 `.env.local`，再报告缺凭据。解析简单 `KEY=value`、quoted 和 unquoted 形式；不要 source 任意 dotenv 文件。
6. 任一来源提供两项值时，验证 live site 是否有匹配 Clarity script，必要时查询 Data Export API。
7. 所有来源都缺值时，报告 Clarity 为 `skipped`，reason 为 `no clarity credentials`。
8. 如果 live site 已安装 Clarity script 但缺 token，只有 script 可验证时才报告 `partial`；否则报告 `skipped`。

安全检查 repo-local dotenv 是否存在：

```bash
for f in .env .env.local; do
  [ -f "$f" ] || continue
  awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{k=$1; v=substr($0,index($0,"=")+1); if (k ~ /^CLARITY_(ID|TOKEN)$/) printf "%s=%s len=%d\n", k, (v=="" ? "empty" : "set"), length(v)}' "$f"
done
```

注入代码或 provider env 前 trim project id。复制 UI 值或 `printf '%s\n'` 可能带换行，造成错误脚本 URL。

## 接入

浏览器/runtime config 只安装 public project id。不要把 `CLARITY_TOKEN` 发送到 Vercel、Next public env、client bundle 或 deployed serverless env，除非有明确 server-side collector 需要。

本地 Vercel deploy 时，如果 working copy 含 Clarity token，确保 `.vercelignore` 排除 `.env` 和 `.env.*`，并保留 `.env.example`：

```text
.env
.env.*
!.env.example
```

不要交互式索要 Clarity 凭据。
不要使用旧 env 名称，例如 `CLARITY_PROJECT_ID` 或 `CLARITY_API_TOKEN`。
不要在日志或最终总结中打印 `CLARITY_TOKEN`。

只有真实 project wiring 可验证时，才把 Clarity 标记为完成。
