# Hetzner SSH Hardening

Hetzner 服务器创建后会通过 root 密码登录。为安全起见，应该切换为 SSH 密钥登录并加固 SSH 配置。

**注意**：此流程仅适用于 Hetzner。OVH VPS 默认只用密钥登录，不需要此加固流程。

## 安全守则

1. 在禁用密码登录前，必须先验证密钥登录可用。
2. 每次 SSH 配置变更后，立即用新连接验证密钥登录。
3. 如果加固后失联，使用 Hetzner Cloud Console 的 Rescue 模式或 VNC 控制台恢复。

## 加固步骤

### 1. 准备工作

在本机检查候选公钥：

```bash
ls -la ~/.ssh
for f in ~/.ssh/*.pub; do [ -f "$f" ] && echo "FILE $f" && head -1 "$f"; done
```

用 root 密码登录服务器：

```bash
bash scripts/login-hetzner-server.sh --host <ip> --password '<root-password>'
```

### 2. 检查当前状态

```bash
sshd -T | egrep "permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication"
ss -ltnp | grep -v '127.0.0.1\|::1'
```

高风险信号：
- `PermitRootLogin yes` + `PasswordAuthentication yes`
- `ufw` 未启用
- `fail2ban` 未安装

### 3. 添加管理密钥

在服务器上备份并添加公钥：

```bash
install -d -m 700 /root/.ssh
cp /root/.ssh/authorized_keys /root/.ssh/authorized_keys.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null || true
echo '<YOUR_PUBLIC_KEY>' >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

在本机验证密钥登录：

```bash
ssh -i ~/.ssh/id_ed25519_hetz_01 -o BatchMode=yes root@<ip> 'echo key-login-ok && whoami && hostname'
```

**必须在禁用密码前确认这一步成功。**

### 4. 加固 SSH

```bash
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%Y%m%d%H%M%S)
mkdir -p /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
EOF
sshd -t && systemctl reload ssh
sshd -T | egrep "permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication"
```

如果 `sshd -T` 仍然显示 `passwordauthentication yes`（通常被 50-cloud-init.conf 覆盖），追加到 `/etc/ssh/sshd_config` 末尾：

```bash
printf '\nPermitRootLogin prohibit-password\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPubkeyAuthentication yes\n' >> /etc/ssh/sshd_config
sshd -t && systemctl reload ssh
```

再次从本机新连接验证密钥登录可用。

### 5. 启用 fail2ban

```bash
apt-get update -y
apt-get install -y fail2ban
cat > /etc/fail2ban/jail.local <<'EOF'
[sshd]
enabled = true
port = ssh
logpath = %(sshd_log)s
backend = systemd
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable --now fail2ban
fail2ban-client status sshd
```

### 6. 启用 ufw 防火墙

```bash
yes | ufw reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
# 按需开放其他端口
# ufw allow 80/tcp
# ufw allow 443/tcp
yes | ufw enable
ufw status verbose
```

### 7. 关闭不必要的公共服务

```bash
ss -ltnp
# 检查是否有不必要的监听，例如 cups (631)
systemctl disable --now cups 2>/dev/null || true
```

## 验收标准

加固完成的标志：

- [ ] 密钥登录可用（新 SSH 连接验证）
- [ ] 密码登录已禁用
- [ ] fail2ban 活跃，sshd jail 已启用
- [ ] ufw 已启用，仅开放必要端口
- [ ] 无不必要的公共服务监听

## 常见问题

- **Ubuntu 云镜像的 cloud-init 覆盖**：`/etc/ssh/sshd_config.d/50-cloud-init.conf` 可能强制 `PasswordAuthentication yes`。用 `sshd -T` 确认最终值，必要时在 `/etc/ssh/sshd_config` 末尾追加覆盖。
- **加固后无法登录**：通过 Hetzner Cloud Console → 服务器 → Rescue → 挂载磁盘恢复 `/root/.ssh/authorized_keys`。
