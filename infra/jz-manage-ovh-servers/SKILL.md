---
name: jz-manage-ovh-servers
description: 管理 OVH VPS 服务器：创建（含购买、rebuild、注入 SSH 公钥）、获取登录方式、SSH 登录、删除。在创建、删除服务器时使用。
---

# jz-manage-ovh-servers

管理 OVH VPS 服务器的完整生命周期。

## 前置条件

- OVH API 凭证（应用密钥、消费者密钥）
- 本机 SSH 密钥对（默认 `~/.ssh/id_ed25519_ovh`）
- 环境变量配置见 `references/env.example`

## 脚本

所有脚本从 skill 目录运行。

### 创建服务器

购买新 VPS → 等待交付 → rebuild（注入 SSH 公钥）→ 等待 SSH 可达 → 输出服务器信息。

```bash
# 查看可用方案和数据中心
tsx scripts/create-ovh-server.ts --list-plans

# Dry-run：检查可下单但不实际执行
tsx scripts/create-ovh-server.ts --dry-run

# 创建一台 VPS
tsx scripts/create-ovh-server.ts \
  --plan "essential" \
  --os "Ubuntu 24.04" \
  --ssh-key ~/.ssh/id_ed25519_ovh \
  --datacenter "BHS"

# 批量创建
tsx scripts/create-ovh-server.ts --count 2
```

参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--dry-run` | - | 只检查不执行 |
| `--list-plans` | - | 列出可用方案 |
| `--plan` | `essential` | VPS 方案（essential, comfort, elite） |
| `--os` | `Ubuntu 24.04` | 操作系统 |
| `--ssh-key` | `~/.ssh/id_ed25519_ovh` | SSH 私钥路径（公钥需同路径 .pub） |
| `--ssh-user` | `ubuntu` | SSH 登录用户 |
| `--datacenter` | 自动选择 | 数据中心代码（如 BHS, GRA, SBG） |
| `--timeout-min` | `60` | 最长等待时间（分钟） |
| `--count` | `1` | 创建数量 |
| `--name-prefix` | `ovh-vps` | 服务器 displayName 前缀 |

### 删除服务器

终止 VPS（不可逆）。

```bash
# Dry-run
tsx scripts/delete-ovh-server.ts --service vps-xxxxxxxx.vps.ovh.ca --dry-run

# 确认删除
tsx scripts/delete-ovh-server.ts --service vps-xxxxxxxx.vps.ovh.ca --confirm
```

参数：

| 参数 | 说明 |
|------|------|
| `--service` | VPS 服务名（如 `vps-xxxxxxxx.vps.ovh.ca`） |
| `--dry-run` | 只列出将要删除的服务器 |
| `--confirm` | 确认执行删除（必加） |

### 登录服务器

SSH 登录。使用 `id_ed25519_ovh` 私钥 + `ubuntu` 用户。

```bash
# 交互式登录
bash scripts/login-ovh-server.sh --host <ip-or-host>

# 执行远程命令
bash scripts/login-ovh-server.sh --host <ip-or-host> --cmd 'whoami && hostname && uptime'

# 指定用户
bash scripts/login-ovh-server.sh --host <ip-or-host> --user root

# 指定密钥
bash scripts/login-ovh-server.sh --host <ip-or-host> --key ~/.ssh/my-other-key
```

参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | - | 服务器 IP 或主机名（必填） |
| `--user` | `ubuntu` | SSH 用户 |
| `--key` | `~/.ssh/id_ed25519_ovh` | SSH 私钥路径 |
| `--cmd` | - | 执行远程命令后退出 |

注意：OVH VPS 不支持 root 密码登录，必须使用 SSH 密钥。默认用户是 `ubuntu`。

## 环境变量

参见 `references/env.example`。脚本自动读取：
1. 当前目录的 `.env` 文件
2. Shell 已导出的环境变量

## 常见问题

- rebuild 后主机 key 变更：脚本自动执行 `ssh-keygen -R <ip>` 清理旧条目。
- 只用 `sshKeyName`（控制台保存的 key 名）在 rebuild 时不一定注入公钥：本脚本强制使用 `publicSshKey` 字段确保注入可靠。
- 删除操作不可逆，请确认后再加 `--confirm`。
