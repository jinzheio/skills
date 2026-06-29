---
name: jz-check-cloud-agent
description: 诊断和运维云端 agent 部署。登录服务器检查 OpenClaw agent 和 Hermes agent 的运行状态，排查 Telegram 消息异常、cron job 故障、Codex OAuth 过期、home channel 丢失、support 邮件接收，并通过 SSH 隧道打开远程 Chrome 桌面。触发词包括：agent 不工作、agent 没回复、hermes agent、codex 用量、fallback、cron job 失败、Codex OAuth、home channel、gateway、打开远程桌面、打开 agent 远程桌面、远程 Chrome、noVNC、support 邮箱、客户邮件、clawsimplesupport 群。当问题涉及 Hermes agent 处理邮件或群内回复时，优先按 Hermes 诊断，不要默认改走 OpenClaw support-inbox cron。
---

# 云端 Agent 诊断

## 目标

用于检查云端部署中 agent 的运行状态：

- OpenClaw agent「{{ config.openclaw.agent_name }}」：运行在 ClawSimple 部署目录的 OpenClaw 配置与服务里。
- Hermes agent「{{ config.hermes.agent_display_name }}」：运行在 `{{ config.hermes.home_dir }}`，systemd 服务通常是 `{{ config.hermes.gateway_service }}.service`。

默认只做读取和诊断。需要修改服务器配置、重启服务、导入 OAuth、修改 Hermes/OpenClaw 文件时，先说明改动点和验证方式。修改后必须复核 owner/group/mode。

## 配置

本 skill 依赖全局配置文件 `~/.config/skills/jz-check-cloud-agent.yaml`。首次使用时，将 skill 目录下的 `config.example.yaml` 复制到该路径并填入实际值。

也支持将配置文件放在 skill 本地目录（`config.yaml`），作为未配置全局文件时的回退。优先级：`~/.config/skills/jz-check-cloud-agent.yaml` > `./config.yaml`（skill 目录）。

结构如下：

```yaml
deployments:
  - id: "<deployment-id>"
    display_name: "<name>"
    user_email: "<email>"
    server:
      ip: "<ip>"
      ssh_user: "root"
      ssh_identity_file: "~/.ssh/<key>"
      install_dir: "<install-dir>"
    openclaw:
      state_dir: "<install-dir>/.openclaw"
      agent_name: "<agent-name>"
    hermes:
      home_dir: "<install-dir>/.hermes/main"
      agent_dir: "<install-dir>/.hermes-agent/hermes-agent"
      gateway_service: "hermes-gateway-<suffix>.service"
      agent_display_name: "<display-name>"
    telegram:
      home_channel_id: "<chat-id>"
      home_channel_name: "<name>"
      support_group_name: "<group-name>"
      support_group_chat_id: "<chat-id>"
    local_repo: "<local-repo-path>"
```

所有固定信息从该配置文件读取，skill 正文不再硬编码。

**配置字段说明**（`[required]` 必须填写，`[optional]` 可留空或删除）：

| 字段 | 要求 | 说明 |
|------|------|------|
| `id` | required | 唯一标识，如 `prod-aone` |
| `display_name` | required | 报告和触发规则中使用的可读名称 |
| `user_email` | required | 部署负责人邮箱 |
| `server.ip` | required | 服务器公网 IPv4 |
| `server.ssh_user` | required | SSH 登录用户 |
| `server.ssh_identity_file` | required | SSH 私钥路径 |
| `server.install_dir` | required | 应用根目录 |
| `openclaw.state_dir` | required | OpenClaw 状态/配置目录 |
| `openclaw.agent_name` | required | openclaw.json 中的 agent 名称 |
| `hermes.home_dir` | required | Hermes HERMES_HOME 目录 |
| `hermes.agent_dir` | required | Hermes-agent 安装目录 |
| `hermes.gateway_service` | required | Hermes gateway systemd 服务名 |
| `hermes.agent_display_name` | required | 报告和触发规则中使用的显示名称 |
| `remote_desktop` | optional | 整块删除则跳过远程桌面功能 |
| `telegram.home_channel_id` | required | agent 归属 Telegram channel 的 chat ID |
| `telegram.home_channel_name` | required | home channel 可读名称 |
| `telegram.support_group_name` | required | support 讨论群名称 |
| `telegram.support_group_chat_id` | required | support 群 chat ID |
| `local_repo` | required | 本地仓库路径 |

**读取并校验配置的函数**（在需要时通过 Python 解析）：

```python
import yaml, os, sys

REQUIRED_FIELDS = [
    # (dotted key, human label)
    ("id", "Deployment ID"),
    ("display_name", "Display name"),
    ("user_email", "User email"),
    ("server.ip", "Server IP"),
    ("server.ssh_user", "SSH user"),
    ("server.ssh_identity_file", "SSH identity file"),
    ("server.install_dir", "Install directory"),
    ("openclaw.state_dir", "OpenClaw state directory"),
    ("openclaw.agent_name", "OpenClaw agent name"),
    ("hermes.home_dir", "Hermes home directory"),
    ("hermes.agent_dir", "Hermes agent directory"),
    ("hermes.gateway_service", "Hermes gateway service"),
    ("hermes.agent_display_name", "Hermes agent display name"),
    ("telegram.home_channel_id", "Telegram home channel ID"),
    ("telegram.home_channel_name", "Telegram home channel name"),
    ("telegram.support_group_name", "Support group name"),
    ("telegram.support_group_chat_id", "Support group chat ID"),
    ("local_repo", "Local repo path"),
]

PLACEHOLDER_PATTERNS = [
    "you@example.com",
    "1.2.3.4",
    "-1001234567890",
    "-1009876543210",
    "My Home Channel",
    "My Support Group",
    "My Agent",
    "my-agent",
    "example-deployment",
    "Example Deployment",
    "~/Projects/myapp",
    "/opt/myapp",
]

def _get_nested(d: dict, dotted_key: str):
    keys = dotted_key.split(".")
    val = d
    for k in keys:
        if not isinstance(val, dict):
            return None
        val = val.get(k)
    return val

def validate_config(cfg: dict):
    """Abort with a clear message if any required field is missing or still a placeholder."""
    missing = []
    still_placeholder = []
    for key, label in REQUIRED_FIELDS:
        val = _get_nested(cfg, key)
        if val is None or val == "":
            missing.append(f"  - {label} ({key}): not set")
        elif isinstance(val, str) and val.strip() in PLACEHOLDER_PATTERNS:
            still_placeholder.append(f"  - {label} ({key}): still placeholder \"{val.strip()}\"")
    errors = []
    if missing:
        errors.append("Missing required fields:\n" + "\n".join(missing))
    if still_placeholder:
        errors.append("Fields still using example values:\n" + "\n".join(still_placeholder))
    if errors:
        msg = "\n\n".join(errors)
        msg += (
            "\n\nEdit ~/.config/skills/jz-check-cloud-agent.yaml and replace every"
            " placeholder with your real values.  See config.example.yaml in the"
            " skill directory for field descriptions."
        )
        print(msg, file=sys.stderr)
        sys.exit(1)

def load_config(deployment_id: str | None = None) -> dict:
    """Load check-cloud-agent config, validate required fields, and return the
    matching deployment.  Aborts if required fields are missing or placeholder."""
    # Priority: global config > skill-local config
    global_path = os.path.expanduser("~/.config/skills/jz-check-cloud-agent.yaml")
    local_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    path = global_path if os.path.exists(global_path) else local_path
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config not found. Copy config.example.yaml to {global_path} and fill in your values."
        )
    with open(path) as f:
        data = yaml.safe_load(f)
    deployments = data.get("deployments", [])
    if not deployment_id:
        deployment_id = os.environ.get("CAO_DEPLOYMENT_ID")
    if deployment_id:
        for d in deployments:
            if d.get("id") == deployment_id or d.get("display_name", "").lower() == deployment_id.lower():
                validate_config(d)
                return d
    cfg = deployments[0] if deployments else {}
    validate_config(cfg)
    return cfg

cfg = load_config()
```

## 触发规则

用户提到「{{ config.hermes.agent_display_name }}」时，默认指 {{ config.display_name }} 上的 Hermes agent，不要先使用通用 support inbox、本地邮箱检查或 OpenClaw cron skill。

以下说法都应触发本 skill：

- `hermes agent {{ config.hermes.agent_display_name }}`
- `{{ config.hermes.agent_display_name }}不工作`
- `{{ config.hermes.agent_display_name }}没回复`
- `{{ config.hermes.agent_display_name }}查看客户邮件`
- `客户邮件接收和拟定回复`
- `{{ config.telegram.support_group_name }} 群`
- `{{ config.hermes.agent_display_name }}在群里负责拟定回复`
- `Hermes cron job 失败`
- `Codex OAuth`
- `home channel`
- `codex 用量`
- `fallback`
- `打开远程桌面`
- `打开 agent 远程桌面`
- `打开远程 Chrome`
- `noVNC`

若用户要求"{{ config.hermes.agent_display_name }}直接处理邮件，不要通过 OpenClaw"，检查重点应放在 Hermes 的 cron 配置、sessions、gateway 日志、Codex auth、Telegram home channel 和 `hermes_cli.main status`。只有在用户明确要求排查旧 OpenClaw support-inbox 任务时，才检查 `{{ config.openclaw.state_dir }}/cron` 里的 support inbox job。

若用户要求配置、验证或排查 Hermes 原生模型 fallback，读取
[`references/hermes-native-fallback.md`](references/hermes-native-fallback.md)。
普通状态检查不加载该 reference。

若用户要求打开远程桌面、远程 Chrome 或 noVNC，读取
[`references/open-remote-desktop.md`](references/open-remote-desktop.md)。
连接地址和 SSH 参数从 `~/.config/skills/jz-check-cloud-agent/<deployment>.yaml` 读取，不把实际地址写入 skill。

## 步骤

### 0. 加载配置

每次执行前，先从 `~/.config/skills/jz-check-cloud-agent.yaml` 加载当前 deployment 配置。后续步骤中的路径、ID、名称均从 `cfg` 对象取值，不再使用硬编码。

如果机器离线或需要快速概览，可以用 `--list` 模式列出所有已知 deployment 的基本信息（不执行任何 SSH）。

### 1. 先查数据库确认目标

在本地仓库执行：

```bash
cd {{ config.local_repo }}
DATABASE_URL=$(sed -n 's/^DATABASE_URL="\([^"]*\)"/\1/p' .env)
psql "$DATABASE_URL" -P pager=off -c "
select
  s.id,
  s.display_name,
  s.status,
  s.active,
  s.ai_source,
  s.last_model,
  s.telegram_username,
  u.email,
  s.server_fingerprint->>'deploy_provider' as provider,
  s.server_fingerprint->>'server_ipv4' as ip,
  s.server_fingerprint->>'server_name' as server_name,
  s.server_fingerprint->>'runtime_mode' as runtime,
  s.server_fingerprint->'agent_runtimes' as agent_runtimes
from install_sessions s
left join \"user\" u on u.id = s.user_id
where s.id = '{{ config.id }}'
   or lower(coalesce(s.display_name,'')) = '{{ config.display_name | lower }}'
order by s.created_at desc
limit 5;
"
```

如果 DB 指向的 IP 与 `{{ config.server.ip }}` 不一致，以 DB 中 active deployment 为准，并在回复里说明差异。

### 2. 登录服务器

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=no \
  -i {{ config.server.ssh_identity_file }} {{ config.server.ssh_user }}@{{ config.server.ip }}
```

若 SSH 在握手阶段偶发 `kex_exchange_identification: Connection closed`，先等 15-30 秒后重试。先用 `ping`、`nc -vz {{ config.server.ip }} 22`、`nc -vz {{ config.server.ip }} 3000` 判断机器是否在线，不要直接重启机器。

### 2.1 打开远程桌面

仅当用户要求打开远程桌面、打开 agent 远程桌面、远程 Chrome 或 noVNC 时，读取
[`references/open-remote-desktop.md`](references/open-remote-desktop.md)。

先确认远端 noVNC 只监听 loopback，再建立 SSH 隧道。不要把远端 `6080` 端口开放到公网。

### 3. 基础服务检查

```bash
hostname
date
systemctl is-active clawsimple clawsimple-jobs {{ config.hermes.gateway_service }} 2>/dev/null || true
systemctl status clawsimple clawsimple-jobs {{ config.hermes.gateway_service }} --no-pager -l
journalctl -u clawsimple -n 120 --no-pager
journalctl -u clawsimple-jobs -n 120 --no-pager
journalctl -u {{ config.hermes.gateway_service }} -n 160 --no-pager
```

关注：

- `clawsimple-jobs` 是否 active。
- `{{ config.hermes.gateway_service }}` 是否 active。
- `clawsimple` 若 failed，先看是否影响 OpenClaw agent「{{ config.openclaw.agent_name }}」实际入口，再判断是否需要修。
- 日志里是否有 `No Codex credentials stored`、`No home channel`、`NoneType object is not iterable`、Telegram network timeout、cron scheduler error。

### 4. 检查 Hermes agent「{{ config.hermes.agent_display_name }}」

运行（agent_dir 为 hermes-agent 安装目录，由配置提供）：

```bash
sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:{{ config.hermes.agent_dir }}/node_modules/.bin:/usr/bin:{{ config.server.install_dir }}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main status
```

正常状态应包含：

- `Model: gpt-5.5`
- `Provider: OpenAI Codex`
- `OpenAI Codex ✓ logged in`
- `Telegram ✓ configured (home: {{ config.telegram.home_channel_id }})`
- `Gateway Service Status: running`
- `Scheduled Jobs: N active, N total`（数量可随用户配置变化）

如果提示没有 home channel，写入 `{{ config.hermes.home_dir }}/.env`：

```env
TELEGRAM_HOME_CHANNEL="{{ config.telegram.home_channel_id }}"
TELEGRAM_HOME_CHANNEL_NAME="{{ config.telegram.home_channel_name }}"
```

然后重启：

```bash
systemctl restart {{ config.hermes.gateway_service }}
```

### 5. 检查 Codex OAuth

先看结构，不要输出 token 原文：

```python
import json, os, datetime
p = "{{ config.hermes.home_dir }}/auth.json"
d = json.load(open(p))
st = (d.get("providers") or {}).get("openai-codex") or {}
toks = st.get("tokens") or {}
pool = (d.get("credential_pool") or {}).get("openai-codex") or []
print("auth_mtime", datetime.datetime.fromtimestamp(os.path.getmtime(p), datetime.timezone.utc).isoformat())
print("provider_state", bool(st))
print("has_access", bool(toks.get("access_token")))
print("has_refresh", bool(toks.get("refresh_token")))
print("pool_entries", len(pool))
print("active_provider", d.get("active_provider"))
```

如果用户要求重新登录 Codex OAuth：

```bash
ssh -tt -o BatchMode=yes -o StrictHostKeyChecking=no \
  -i {{ config.server.ssh_identity_file }} {{ config.server.ssh_user }}@{{ config.server.ip }} \
  'sudo -u clawsimple env HOME={{ config.server.install_dir }} HERMES_HOME={{ config.hermes.home_dir }} PATH={{ config.hermes.agent_dir }}/venv/bin:{{ config.hermes.agent_dir }}/node_modules/.bin:/usr/bin:{{ config.server.install_dir }}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main auth add openai-codex'
```

把显示出的 `https://auth.openai.com/codex/device` 和 code 发给用户。用户完成授权后，确认是否写入 `credential_pool.openai-codex`。

当前 Hermes cron resolver 需要 `providers.openai-codex.tokens`。如果 OAuth 只写进 `credential_pool.openai-codex`，把最新 credential 激活成 provider state。操作前备份 `auth.json`，操作后保持 `clawsimple:clawsimple 600`，再用 `resolve_codex_runtime_credentials()` 验证。

### 5.1 检查 Hermes 原生模型 fallback

仅当用户要求增加 fallback、Codex 用尽后继续工作、验证 fallback，或日志显示主模型失败后没有切换时，读取
[`references/hermes-native-fallback.md`](references/hermes-native-fallback.md)。

基础检查：

```bash
sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:/usr/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main fallback list
```

不要用自建代理或修改 `run_agent.py` 实现已有的 Hermes 原生 fallback。不要仅凭 key 名判断 Kimi 区域；先按 reference 验证 endpoint。

### 6. 检查 Hermes Codex streaming 错误

若用户看到：

```text
Non-retryable error (HTTP None)
'NoneType' object is not iterable
```

先看最新 request dump：

```python
import json, glob, os
for p in sorted(glob.glob("{{ config.hermes.home_dir }}/sessions/request_dump_*"), key=os.path.getmtime)[-3:]:
    d = json.load(open(p))
    body = (d.get("request") or {}).get("body") or {}
    print("---", p)
    print("reason", d.get("reason"), "error", d.get("error"))
    print("model", body.get("model"), "stream", repr(body.get("stream")), "keys", sorted(body.keys()))
```

已知现象：OpenAI Python SDK 处理 `chatgpt.com/backend-api/codex` streaming events 时，可能在已经收到 `response.output_text.delta` 后抛 `TypeError: 'NoneType' object is not iterable`。

现有修复点在：

```text
{{ config.hermes.agent_dir }}/run_agent.py
```

搜索：

```bash
grep -n "Codex Responses stream parser raised" {{ config.hermes.agent_dir }}/run_agent.py
```

应能看到 TypeError fallback：当 stream parser 抛 `NoneType` 且已有 collected output/text delta 时，合成 `SimpleNamespace(output=..., status="completed")`。如果升级 Hermes 后这个补丁消失，按同一逻辑补回，先备份文件，执行：

```bash
python3 -m py_compile {{ config.hermes.agent_dir }}/run_agent.py
systemctl restart {{ config.hermes.gateway_service }}
```

用最小请求验证：

```bash
cd {{ config.server.install_dir }}
timeout 120 sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:{{ config.hermes.agent_dir }}/node_modules/.bin:/usr/bin:{{ config.server.install_dir }}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main chat \
    -Q --ignore-rules --max-turns 1 -q "Reply exactly: OK"
```

通过时应返回 `OK`，exit code 为 0。

### 7. 检查 {{ config.hermes.agent_display_name }}的客户邮件接收和拟回复任务

{{ config.hermes.agent_display_name }}是 Hermes agent。排查客户邮件接收、`{{ config.telegram.support_group_name }}` 群内拟回复、support 邮箱定时检查时，先检查 Hermes cron，不要先查 OpenClaw cron。

先列出 Hermes cron：

```bash
sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:{{ config.hermes.agent_dir }}/node_modules/.bin:/usr/bin:{{ config.server.install_dir }}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main cron list
```

再直接检查 job 文件，避免 CLI 摘要漏掉 prompt 内容：

```python
import json
p = "{{ config.hermes.home_dir }}/cron/jobs.json"
d = json.load(open(p))
jobs = d.get("jobs") if isinstance(d, dict) else d
for job in jobs or []:
    text = json.dumps(job, ensure_ascii=False).lower()
    if any(k in text for k in ["support", "mail", "gmail", "inbox", "{{ config.telegram.support_group_name }}", "{{ config.hermes.agent_display_name }}"]):
        print(json.dumps(job, ensure_ascii=False, indent=2)[:6000])
```

如果没有 support/mail/gmail 相关 Hermes cron，结论是：{{ config.hermes.agent_display_name }}当前没有负责 support 邮件的 Hermes 定时任务。不要把旧的 `{{ config.openclaw.state_dir }}/cron/jobs.json` 里的 `support-inbox-hourly` 当成 {{ config.hermes.agent_display_name }}任务。

检查 Hermes 是否有读取 Gmail 所需配置。只输出 key 是否存在，不输出值：

```python
from pathlib import Path
keys = [
    "HUB_API_KEY",
    "MATON_API_KEY",
    "LOCAL_MATON_API_KEY",
    "SUPPORT_INBOX_QUERY",
    "SUPPORT_INBOX_STATE_PATH",
]
env = {}
for p in [Path("{{ config.server.install_dir }}/.env.app"), Path("{{ config.hermes.home_dir }}/.env")]:
    if not p.exists():
        continue
    for line in p.read_text().splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
for k in keys:
    print(k, "set" if env.get(k) else "missing")
```

Hermes 直连 support 邮件的期望设计：

- 定时任务属于 `{{ config.hermes.home_dir }}/cron/jobs.json`。
- 状态文件放在 `{{ config.hermes.home_dir }}/support-inbox/state.json`。
- 读取 Gmail 使用 Maton/Gmail API key，环境变量优先用 `HUB_API_KEY` 或 `MATON_API_KEY`。
- 只把"新客户邮件 + 客户上下文 + 建议回复"发到 `{{ config.telegram.support_group_name }}` 群。
- 不自动发邮件，不标记 Gmail 已读，不删除邮件。
- 只有 Telegram 群消息成功生成后，才把 message id 写入 Hermes support state。
- 邮件是营销推广、冷邮件或垃圾邮件时，也要在群里给出简短判断，例如"无需回复/可忽略"，避免状态卡住。

如果需要创建 Hermes 直连 cron，先把 prompt 写到临时文件并人工检查，不要把 secret 写入 prompt：

```bash
cat >/tmp/hermes-support-inbox-prompt.txt <<'PROMPT'
你是 {{ config.display_name }} 上的 Hermes agent「{{ config.hermes.agent_display_name }}」，负责检查 ClawSimple support 邮箱并在 {{ config.telegram.support_group_name }} 群里拟定回复。

每次运行只处理一封最新未处理邮件。

读取来源：
- Gmail 通过 Maton gateway 读取。
- 查询默认使用：to:support@clawsimple.com newer_than:7d
- Maton API key 从环境变量 HUB_API_KEY 或 MATON_API_KEY 读取，不要输出 key。
- 运行状态放在 {{ config.hermes.home_dir }}/support-inbox/state.json。

处理规则：
1. 不发送邮件。
2. 不修改 Gmail 状态。
3. 不调用 OpenClaw cron。
4. 不使用 {{ config.openclaw.state_dir }}/cron/jobs.json。
5. 如果没有新邮件，返回 NO_REPLY。
6. 如果是营销推广或垃圾邮件，仍然给 {{ config.telegram.support_group_name }} 群发一条简短判断，并把它记为 processed。
7. 如果是客户问题，输出：

New support email

From: ...
To: ...
Subject: ...

Original email:
...

Customer context:
...

Suggested reply:
```text
...
```

客户上下文优先使用 ClawSimple 本地仓库已有的 support context helper 或只读数据库查询。查不到时写：No matching deployment context found.

完成后，把已处理 message id 写入 {{ config.hermes.home_dir }}/support-inbox/state.json。
PROMPT
```

创建 cron 前先确认 Hermes CLI 支持的参数：

```bash
sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:{{ config.hermes.agent_dir }}/node_modules/.bin:/usr/bin:{{ config.server.install_dir }}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main cron create --help
```

创建示例，使用 `telegram:{{ config.telegram.support_group_chat_id }}` 投递到 `{{ config.telegram.support_group_name }}` 群：

```bash
sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:{{ config.hermes.agent_dir }}/node_modules/.bin:/usr/bin:{{ config.server.install_dir }}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main cron create \
    --name "ClawSimple support inbox draft reply" \
    --deliver "telegram:{{ config.telegram.support_group_chat_id }}" \
    --workdir {{ config.server.install_dir }} \
    "every 2h" \
    "$(cat /tmp/hermes-support-inbox-prompt.txt)"
```

创建后复核：

```bash
sudo -u clawsimple env HOME={{ config.server.install_dir }} HERMES_HOME={{ config.hermes.home_dir }} \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main cron list
stat -c "%U:%G %a %n" {{ config.hermes.home_dir }}/cron/jobs.json
```

手动试跑时，先选中刚创建的 job id：

```bash
sudo -u clawsimple env \
  HOME={{ config.server.install_dir }} \
  HERMES_HOME={{ config.hermes.home_dir }} \
  PATH={{ config.hermes.agent_dir }}/venv/bin:{{ config.hermes.agent_dir }}/node_modules/.bin:/usr/bin:{{ config.server.install_dir }}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  VIRTUAL_ENV={{ config.hermes.agent_dir }}/venv \
  {{ config.hermes.agent_dir }}/venv/bin/python -m hermes_cli.main cron run <JOB_ID>
```

然后检查：

```bash
journalctl -u {{ config.hermes.gateway_service }} -n 160 --no-pager
find {{ config.hermes.home_dir }}/cron/output -maxdepth 3 -type f -printf "%TY-%Tm-%Td %TH:%TM:%TS %p\n" | sort | tail
python3 -m json.tool {{ config.hermes.home_dir }}/support-inbox/state.json 2>/dev/null || true
```

如果 Maton/Gmail key 缺失，先汇报缺失，不要凭空改用 Himalaya。Himalaya 是 IMAP/SMTP skill，只有在服务器已配置 support 邮箱 IMAP/SMTP 时才适用。

### 8. 检查 OpenClaw agent「{{ config.openclaw.agent_name }}」

先看 OpenClaw 配置与 agent 列表：

```bash
stat -c "%U:%G %a %n" {{ config.openclaw.state_dir }} {{ config.openclaw.state_dir }}/openclaw.json
python3 - <<'PY'
import json
p = "{{ config.openclaw.state_dir }}/openclaw.json"
d = json.load(open(p))
print("top_keys", sorted(d.keys()))
agents = d.get("agents") or d.get("agent") or {}
print("agents_type", type(agents).__name__)
print(json.dumps(agents, ensure_ascii=False, indent=2)[:5000])
PY
find {{ config.openclaw.state_dir }}/agents -maxdepth 3 -type f \( -name "models.json" -o -name "auth-profiles.json" -o -name "auth-state.json" \) -printf "%u:%g %m %s %p\n" | sort
```

定位名称为「{{ config.openclaw.agent_name }}」的 agent 后，检查它的：

- agent id 与目录。
- model 配置。
- Telegram account 是否启用。
- `auth-profiles.json` / `models.json` 是否存在且权限为 `clawsimple:clawsimple 600`。
- 是否与 Hermes「{{ config.hermes.agent_display_name }}」抢同一个 Telegram bot polling。若 Hermes 是 active runtime，OpenClaw 对应 Telegram polling 应被禁用。

### 9. 修改后的权限复核

任何修改后都执行：

```bash
stat -c "%U:%G %a %n" \
  {{ config.hermes.home_dir }}/.env \
  {{ config.hermes.home_dir }}/auth.json \
  {{ config.hermes.home_dir }}/config.yaml \
  {{ config.hermes.home_dir }}/cron/jobs.json \
  {{ config.hermes.home_dir }}/support-inbox/state.json \
  {{ config.hermes.agent_dir }}/run_agent.py \
  {{ config.openclaw.state_dir }}/openclaw.json 2>/dev/null || true
```

常见期望：

- Hermes `.env` / `auth.json` / `config.yaml`：`clawsimple:clawsimple 600`
- Hermes patched Python 文件：保持修改前 mode，最近一次为 `clawsimple:clawsimple 664`
- OpenClaw 配置与 agent auth 文件：通常为 `clawsimple:clawsimple 600`

## 汇报格式

最终回复包含：

- DB 指向的 active deployment、IP、runtime。
- `clawsimple`、`clawsimple-jobs`、`{{ config.hermes.gateway_service }}` 状态。
- {{ config.openclaw.agent_name }}：agent id、runtime、model、Telegram polling 状态、主要异常。
- {{ config.hermes.agent_display_name }}：Hermes status、Codex OAuth、Telegram home channel、cron 数量、主要异常。
- {{ config.hermes.agent_display_name }} support 邮件：Hermes cron 是否存在、Maton/Gmail key 是否存在、support state 路径、最新试跑结果、是否投递到 `{{ config.telegram.support_group_name }}`。
- 已做改动、备份文件、验证结果。
- 未解决风险，例如 SSH 间歇断连、Hermes 升级可能覆盖本地补丁。
