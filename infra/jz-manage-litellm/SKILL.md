---
name: jz-manage-litellm
description: 查询和运维 LiteLLM 网关信息。用户要查模型价格、key 是否可用、key 用量、SpendLogs、fallback、预算、blocked/expired 状态、LiteLLM 管理界面、Docker/Postgres 状态，或要求调整 LiteLLM 模型价格、fallback、key 预算和作废 key 时使用。默认只读；修改生产 LiteLLM 配置前必须备份并验证。
---

# LiteLLM 网关运维

## 目标

用于检查 LiteLLM 服务的运行状态、模型价格、key 权限和用量。

默认只做读取：

- 模型价格：`input_cost_per_token`、`output_cost_per_token`、cache 价格。
- key 状态：alias、team、模型权限、spend、budget、blocked、expires、last_active。
- 用量记录：最近 SpendLogs、按 key/model 聚合。
- fallback：读取 `LiteLLM_Config.router_settings`。
- 服务状态：远端 Docker、UI HTTP 状态、Postgres 健康。

涉及修改时，包括调价、fallback、key 预算、作废/恢复 key，先备份相关表，再事务更新，最后重启 LiteLLM 并验证。

不要打印完整 token、provider API key、master key、数据库密码。输出 key 时只显示 alias 或遮罩后的引用。

## 配置

配置放在本机未跟踪目录：

```text
~/.config/skills/jz-manage-litellm/.env
```

第一次使用时，复制同目录下的 `.env.example`：

```bash
cp ~/.config/skills/jz-manage-litellm/.env.example ~/.config/skills/jz-manage-litellm/.env
```

然后填入 SSH 目标、远端 compose 目录、容器名、数据库名等。真实 `.env` 不放入 `jzskills` repo。

脚本会按这个优先级读取配置：

1. `JZ_LITELLM_OPS_ENV` 指向的文件。
2. `~/.config/skills/jz-manage-litellm/.env`。
3. 当前 shell 已导出的环境变量。

## 快速命令

脚本路径：

```bash
./scripts/litellm_ops.sh
```

常用只读查询：

```bash
# 服务、UI、本机端口、容器
./scripts/litellm_ops.sh status

# 模型价格
./scripts/litellm_ops.sh prices

# key 状态汇总和可用 key
./scripts/litellm_ops.sh keys

# 某个 key alias 的状态
./scripts/litellm_ops.sh key test-01

# 最近用量
./scripts/litellm_ops.sh spend

# fallback 配置
./scripts/litellm_ops.sh fallback

# 只打开或输出管理界面地址
./scripts/litellm_ops.sh ui
```

脚本输出已经尽量遮罩敏感信息。不要把完整 `.env`、完整 key、provider secret 贴回用户。

## 操作流程

### 1. 判断用户意图

用户问这些问题时，只读查询：

- “现在模型价格是多少？”
- “哪些 key 能用？”
- “test-01 是否可用？”
- “某个 key 花了多少钱？”
- “fallback 是否配置？”
- “管理界面打不开，检查一下。”

用户明确要求这些操作时，才修改：

- “把价格改成……”
- “作废/恢复某些 key。”
- “把某个 key 额度改成……”
- “增加 fallback。”

### 2. 查询模型价格

优先用脚本：

```bash
./scripts/litellm_ops.sh prices
```

报告时统一说明单位：

- 数据库内字段是 USD/token。
- 对外表格优先换算成 USD / 1M tokens。
- cache read 和 cache creation 单独列出。

### 3. 查询 key 和用量

用：

```bash
./scripts/litellm_ops.sh keys
./scripts/litellm_ops.sh key <alias>
./scripts/litellm_ops.sh spend
```

判断 key 是否可用时同时看：

- `blocked=false`
- `expires` 为空或晚于当前时间
- key 自身预算未耗尽
- team 预算未耗尽
- key 或 team 的 `models` 包含目标模型；空数组通常按全模型处理

只输出 alias、team、预算、spend、状态和模型列表。不要输出完整 token。

### 4. 查询 fallback

用：

```bash
./scripts/litellm_ops.sh fallback
```

检查是否覆盖用户关心的模型。日志里出现 `No fallback model group found` 时，优先检查该模型是否缺少 fallback。

### 5. 处理管理界面打不开

先区分三条路径：

```bash
./scripts/litellm_ops.sh status
./scripts/litellm_ops.sh ui
```

排查顺序：

1. 本机 Tailscale 是否在线。
2. UI 的 Tailscale HTTP 地址是否返回 `200`。
3. 远端 `127.0.0.1:4000/ui/` 是否返回 `200`。
4. Docker 容器是否运行。
5. 日志里是否有启动、DB、auth 或 502 相关错误。

注意：UI 端口通常是 HTTP，不是 HTTPS。浏览器如果自动切到 HTTPS，会失败。

### 6. 修改配置的规则

修改前必须备份相关表，备份放在远端 compose 目录的 `backups/` 下。常见备份：

```bash
pg_dump -t '"LiteLLM_ProxyModelTable"'
pg_dump -t '"LiteLLM_VerificationToken"'
pg_dump -t '"LiteLLM_Config"'
```

修改后必须：

1. 重新查询 DB，确认字段已写入。
2. 重启 LiteLLM 容器。
3. 等 `/ui/` 返回 `200`。
4. 用真实请求或 `/model/info` 验证运行时已加载。
5. 查 SpendLogs 或 key spend，确认计费/权限按预期生效。

默认不要 push、发布或改生产以外的同步配置，除非用户明确要求。

