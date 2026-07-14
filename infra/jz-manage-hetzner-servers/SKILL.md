---
name: jz-manage-hetzner-servers
description: 管理 Hetzner Cloud 服务器：创建、获取登录方式（IP/root密码）、SSH 登录、加固（改为 SSH key 登录）、删除。在创建、删除新的服务器时使用。
---

# jz-manage-hetzner-servers

管理 Hetzner Cloud 服务器的完整生命周期。

## 前置条件

- Hetzner Cloud API Token（在 Hetzner Cloud Console → Security → API Tokens 创建）
- SSH 密钥对（推荐 `~/.ssh/id_ed25519_hetz_01`，用于加固后的 key 登录）
- 环境变量配置见 `references/env.example`

## 脚本

所有脚本从 skill 目录运行。

### 创建服务器

通过 Hetzner Cloud API 创建服务器 → 等待运行 → 输出 IP 和 root 密码。

```bash
# Dry-run：查看将要创建的服务器参数
tsx scripts/create-hetzner-server.ts --dry-run

# 创建一台服务器（使用默认配置）
tsx scripts/create-hetzner-server.ts

# 自定义配置
tsx scripts/create-hetzner-server.ts \
  --name my-server \
  --server-type cx32 \
  --location nbg1 \
  --image ubuntu-24.04 \
  --ssh-key-name my-hetzner-key

# 批量创建
tsx scripts/create-hetzner-server.ts --count 3 --name-prefix web
```

参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--dry-run` | - | 只检查不执行 |
| `--name` | 自动生成 | 服务器名称 |
| `--name-prefix` | `server` | 批量创建时名称前缀 |
| `--server-type` | `cx22` | 服务器类型（cx22, cx32, cpx31 等） |
| `--location` | `nbg1` | 数据中心（nbg1, fsn1, hel1, ash） |
| `--image` | `ubuntu-24.04` | 操作系统镜像 |
| `--ssh-key-name` | - | Hetzner 控制台保存的 SSH key 名称 |
| `--count` | `1` | 创建数量（最多 10） |
| `--timeout-min` | `5` | 最长等待运行时间（分钟） |
| `--wait-ssh` | `false` | 等待 SSH 可达（创建后） |
| `--ssh-user` | `root` | SSH 等待用户 |

创建成功后输出：
- 服务器 ID、名称
- IPv4 / IPv6
- root 密码（仅在创建时返回，请保存）
- 登录命令

### 删除服务器

```bash
# 列出所有服务器
tsx scripts/delete-hetzner-server.ts --list

# Dry-run
tsx scripts/delete-hetzner-server.ts --server-name my-server --dry-run

# 按名称删除
tsx scripts/delete-hetzner-server.ts --server-name my-server --confirm

# 按 ID 删除
tsx scripts/delete-hetzner-server.ts --server-id 12345678 --confirm
```

参数：

| 参数 | 说明 |
|------|------|
| `--list` | 列出所有服务器 |
| `--server-id` | 按 ID 删除 |
| `--server-name` | 按名称删除（删除第一个匹配） |
| `--dry-run` | 只列出将要删除的服务器 |
| `--confirm` | 确认执行删除（必加） |

### 登录服务器

优先使用 SSH 密钥，回退 root 密码。

```bash
# 交互式登录（已知加固过的主机会自动用 key）
bash scripts/login-hetzner-server.sh --host <ip>

# 指定 root 密码
bash scripts/login-hetzner-server.sh --host <ip> --password '<root-password>'

# 指定 SSH 密钥
bash scripts/login-hetzner-server.sh --host <ip> --key ~/.ssh/id_ed25519_hetz_01

# 执行命令
bash scripts/login-hetzner-server.sh --host <ip> --cmd 'whoami && hostname && uptime'
```

参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | - | 服务器 IP 或主机名（必填） |
| `--user` | `root` | SSH 用户 |
| `--key` | `~/.ssh/id_ed25519_hetz_01` | SSH 私钥路径（优先尝试） |
| `--password` | - | root 密码（key 不可用时使用） |
| `--cmd` | - | 执行远程命令后退出 |

### 加固

创建服务器后，建议立即加固。详见 `references/ssh-hardening.md`。

核心步骤：
1. 用 root 密码登录
2. 添加 SSH 公钥到 `/root/.ssh/authorized_keys`
3. 验证 key 登录可用
4. 禁用密码登录、启用 fail2ban、配置 ufw

加固后的主机后续可以用 key 直接登录，无需密码。

## 环境变量

参见 `references/env.example`。脚本自动读取：
1. 当前目录的 `.env` 文件
2. Shell 已导出的环境变量

## 常见问题

- 创建服务器时 root 密码只在 API 响应中返回一次，请立即保存。
- 如果 `sshpass` 未安装，密码登录会回退到交互模式，手动输入密码。
- 删除操作不可逆，请确认后再加 `--confirm`。
- 加固流程见 `references/ssh-hardening.md`，不适用于 OVH 主机。
