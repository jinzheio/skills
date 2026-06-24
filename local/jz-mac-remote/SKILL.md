---
name: jz-mac-remote
description: 通过 Bonjour 名（.local）连接局域网内的另一台 Mac，执行远程命令、同步文件、配置 CC Switch 等操作。触发词包括：连接/登录/远程到 + 机器名（如"连到 iMac"）、传文件到 + 机器名、同步/拷贝 + 文件/配置 + 机器名。适用于局域网内有多台 Mac 且均已开启远程登录（SSH）的场景。
---

# 远程 Mac 连接

## 目标

通过 Bonjour 主机名（`<name>.local`）连接局域网内另一台 Mac，执行：

- 远程命令（包括在远端运行 Claude Code / Codex / shell 脚本）。
- 双向文件传输（本机 ↔ 远端）。
- CC Switch provider 配置同步（仅模型连接信息，不含 MCP/skills）。
- 远程 CLI 工具调用（`brew`、`sqlite3`、`system_profiler` 等）。

## 前置条件

使用本 skill 前，**两台 Mac 都必须满足**：

### 目标 Mac（被控端）

1. **开启远程登录**：系统设置 → 通用 → 共享 → 打开「远程登录」。
2. **允许 SSH 用户**：在「远程登录」中指定允许通过 SSH 访问的用户账号，或设为「所有用户」。
3. **确认 Bonjour 名**：
   ```bash
   # 在目标 Mac 上执行
   scutil --get ComputerName
   ```
   记下这个名称，它就是后续使用的 `<instance>` 名（也称 Bonjour 名 / `.local` 主机名）。

### 本机（控制端）

1. **生成 SSH key（如果还没有）**：
   ```bash
   ssh-keygen -t ed25519 -C "your-email@example.com"
   ```
2. **将公钥上传到目标 Mac**：
   ```bash
   ssh-copy-id -i ~/.ssh/id_ed25519 <user>@<instance>.local
   ```
   或者手动追加到目标 Mac 的 `~/.ssh/authorized_keys`。

   **验证方式**：
   ```bash
   ssh -o ConnectTimeout=5 <user>@<instance>.local "echo ok"
   ```
   应返回 `ok` 且不要求密码。如果提示密码，说明公钥未配置成功。

3. **创建本 skill 的环境文件**（见下一节）。

## 配置

首次使用前，将环境模板复制到本机未跟踪目录并填入实际值：

```bash
cp <skill-dir>/.env.example ~/.config/skills/jz-mac-remote/.env
chmod 600 ~/.config/skills/jz-mac-remote/.env
```

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `JZ_MAC_REMOTE_DEFAULT_INSTANCE` | 是 | 未指定 instance 时的默认 Bonjour 名，如 `my-imac` |
| `JZ_MAC_REMOTE_SSH_USER` | 是 | 远端 Mac 登录用户名 |
| `JZ_MAC_REMOTE_SSH_IDENTITY_FILE` | 是 | 本机 SSH 私钥路径 |
| `JZ_MAC_REMOTE_DEFAULT_DEST` | 否 | 文件传输默认目标路径，默认 `~/Desktop` |

**多台 Mac**：可以为每台 Mac 单独覆盖 SSH 用户和 key。规则：取 instance 名的大写形式，连字符替换为下划线，加上 `_SSH_USER` / `_SSH_IDENTITY_FILE` 后缀。

例如 instance 名为 `my-mac-studio`：
```bash
JZ_MAC_REMOTE_MY_MAC_STUDIO_SSH_USER=<user-on-that-mac>
JZ_MAC_REMOTE_MY_MAC_STUDIO_SSH_IDENTITY_FILE=~/.ssh/id_ed25519_studio
```

### 加载顺序

1. 当前 shell 已导出的同名环境变量。
2. `~/.config/skills/jz-mac-remote/.env`。
3. skill 目录下的 `.env`（fallback，不跟踪到 git）。

## 触发规则

用户提到以下模式时触发本 skill：

- `连接 <名称>`、`登录 <名称>`、`连到 <名称>`、`SSH 到 <名称>`
- `在 <名称> 上执行/运行 <命令>`
- `<名称> 上跑一下 <工具>`
- `把 <文件> 传到 <名称>`
- `从 <名称> 拷贝 <文件>`
- `同步/导出 provider 到 <名称>`
- `检查 <名称> 上的 CC Switch`
- `在 <名称> 上用 Claude Code 做 <任务>`

用户只提到机器名而没有明确说「连接」或「远程」时，根据上下文判断是否为远程操作。不确定时确认意图。

## 步骤

### 1. 解析目标 instance

从用户输入提取 instance name（Bonjour 名，去掉 `.local` 后缀）。

按优先级确定 SSH 连接参数：

- `SSH_USER`：先查 `JZ_MAC_REMOTE_<UPPER_INSTANCE>_SSH_USER`，若无则取 `JZ_MAC_REMOTE_SSH_USER`。
- `SSH_IDENTITY_FILE`：先查 `JZ_MAC_REMOTE_<UPPER_INSTANCE>_SSH_IDENTITY_FILE`，若无则取 `JZ_MAC_REMOTE_SSH_IDENTITY_FILE`。
- 若用户未指定 instance，取 `JZ_MAC_REMOTE_DEFAULT_INSTANCE`。

如果上述任一变量未设置，提示用户先完成[前置条件](#前置条件)和[配置](#配置)小节，不要用猜测值。

### 2. 验证连通性

```bash
ping -c 1 -W 2 <instance>.local
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new \
  -i <SSH_IDENTITY_FILE> <SSH_USER>@<instance>.local "echo 'connected'"
```

**常见问题排查**：

| 现象 | 可能原因 | 操作 |
|------|----------|------|
| `ping: cannot resolve` | Bonjour 名不对或不在同一局域网 | 在目标 Mac 上运行 `scutil --get ComputerName` 确认名称；检查两台 Mac 是否在同一 Wi-Fi / 有线网络 |
| ping 通但 SSH 不通 | 远程登录未开启 | 目标 Mac：系统设置 → 通用 → 共享 → 打开「远程登录」 |
| SSH 提示 `Permission denied` | 公钥未上传或用户名不对 | 运行 `ssh-copy-id -i <key> <user>@<instance>.local`；确认目标 Mac 上的用户名正确 |
| 要求输入密码 | 公钥认证未配置 | 同上，或检查目标 Mac `~/.ssh/authorized_keys` 权限是否为 `600` |

### 3. 操作

#### 3a. 远程命令执行

```bash
ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
  -i <SSH_IDENTITY_FILE> <SSH_USER>@<instance>.local "<command>"
```

支持在远端运行任何 CLI 工具，包括：

- **Claude Code**：`ssh ... "cd /path/to/project && claude -p 'your prompt'"`
- **Codex**：`ssh ... "cd /path/to/project && codex exec 'your prompt'"`
- **系统命令**：`ssh ... "system_profiler SPHardwareDataType"`
- **Shell 脚本**：`ssh ... "bash -s" < local-script.sh`

在远端运行交互式 Agent 时：
- 优先使用非交互参数（如 `claude -p`、`codex exec`）。
- 需要交互时使用 `ssh -t`。
- 先检查远端的工具和项目路径是否存在。

#### 3b. 文件传输（本机 → 远端）

```bash
scp -o StrictHostKeyChecking=accept-new \
  -i <SSH_IDENTITY_FILE> <local_path> <SSH_USER>@<instance>.local:<remote_path>
```

不指定 `<remote_path>` 时，默认传到 `${JZ_MAC_REMOTE_DEFAULT_DEST:-~/Desktop}/`。

支持传目录（`scp -r`）、多个文件、通配符。

#### 3c. 文件传输（远端 → 本机）

```bash
scp -o StrictHostKeyChecking=accept-new \
  -i <SSH_IDENTITY_FILE> <SSH_USER>@<instance>.local:<remote_path> <local_path>
```

### 4. CC Switch provider 同步

> **注意**：此操作传输的 SQL 文件中包含远端 provider 的 API key 和 token。传输完成后建议从目标 Mac 清理临时 SQL 文件。

#### 4a. 导出本机 provider 到远端

```bash
# 转储 providers + provider_endpoints（仅模型连接信息，不含 MCP/skills/usage）
sqlite3 ~/.cc-switch/cc-switch.db ".dump providers" > /tmp/cc-providers-export.sql
sqlite3 ~/.cc-switch/cc-switch.db ".dump provider_endpoints" >> /tmp/cc-providers-export.sql

# 去除 CREATE TABLE 语句，避免与目标 Mac 上已有的表冲突
grep "^INSERT INTO" /tmp/cc-providers-export.sql | \
  sed 's/INSERT INTO /INSERT OR REPLACE INTO /g' > /tmp/cc-providers-import.sql

# 传到远端
scp -o StrictHostKeyChecking=accept-new -i <SSH_IDENTITY_FILE> \
  /tmp/cc-providers-import.sql <SSH_USER>@<instance>.local:~/Desktop/

# 在远端导入（自动备份原数据库）
ssh -o StrictHostKeyChecking=accept-new -i <SSH_IDENTITY_FILE> \
  <SSH_USER>@<instance>.local \
  "cp ~/.cc-switch/cc-switch.db ~/.cc-switch/cc-switch.db.bak-\$(date +%Y%m%d_%H%M%S) && \
   sqlite3 ~/.cc-switch/cc-switch.db < ~/Desktop/cc-providers-import.sql && \
   rm ~/Desktop/cc-providers-import.sql && \
   echo 'Import OK'"

# 清理本机临时文件
rm /tmp/cc-providers-export.sql /tmp/cc-providers-import.sql
```

导入后提醒用户在远端重启 CC Switch 以加载新 provider。

#### 4b. 查看远端 CC Switch provider 列表

```bash
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new \
  -i <SSH_IDENTITY_FILE> <SSH_USER>@<instance>.local \
  "sqlite3 ~/.cc-switch/cc-switch.db \"SELECT app_type, name FROM providers ORDER BY app_type, sort_index;\""
```

## 安全约束

- `~/.config/skills/jz-mac-remote/.env` 必须 `chmod 600`，不提交到 git。
- SSH 私钥路径、用户名、IP 地址不输出到回复正文中。只在执行命令时使用，不在报告里展示。
- 传输含 token 的文件后提醒用户清理两端临时文件。
- 远程命令执行前，如涉及破坏性操作（`rm -rf`、`git reset --hard` 等），先向用户确认。

## 汇报格式

每次操作完成后汇报：

- 目标 instance（Bonjour 名）、连通性状态。
- 执行的命令及结果摘要。
- 文件传输：源路径 → 目标路径、传输大小。
- CC Switch 同步：provider 数量、导入前后对比。
- 异常情况：错误信息、可能原因、建议操作。
