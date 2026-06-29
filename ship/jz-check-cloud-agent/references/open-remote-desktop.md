# 打开远程桌面

用户要求打开远程桌面、远程 Chrome 或 noVNC 时读取本文。

## 私有配置

从 `~/.config/skills/jz-check-cloud-agent/<deployment>.yaml` 读取连接参数。文件名使用 deployment display name 的小写形式，例如 `prodaone.yaml`。

```yaml
deployment:
  id: "<deployment-id>"
  display_name: "<display-name>"
server:
  ip: "<server-ip>"
  ssh_user: "root"
  ssh_identity_file: "~/.ssh/<key>"
remote_desktop:
  local_host: "127.0.0.1"
  local_port: 6080
  remote_host: "127.0.0.1"
  remote_port: 6080
  path: "/vnc.html"
```

该文件只能保存在本机，权限设为 `600`。不要把实际 IP、SSH key 路径或凭据写进 skill 仓库。

## 打开步骤

先读取私有配置并展开 `~`。检查本机端口是否已被占用：

```bash
lsof -nP -iTCP:6080 -sTCP:LISTEN
```

检查远端 noVNC。服务必须监听 `127.0.0.1` 或 `::1`，不要监听公网地址：

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=no \
  -i <ssh_identity_file> <ssh_user>@<server_ip> \
  'ss -ltnp | grep ":6080 "; curl -sS -I --max-time 5 http://127.0.0.1:6080/vnc.html | head'
```

正常结果应包含：

- `127.0.0.1:6080` 正在监听。
- `vnc.html` 返回 HTTP 200。
- 远端 Chrome、Xvfb、x11vnc、websockify/noVNC 正在运行。

建立 SSH 隧道：

```bash
ssh -N \
  -L 127.0.0.1:6080:127.0.0.1:6080 \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -i <ssh_identity_file> \
  <ssh_user>@<server_ip>
```

隧道需要持续运行。若由 agent 执行，保留对应终端 session，不要在任务结束前关闭。若本机 `6080` 已被占用，选一个空闲端口，例如 `16080`，并相应修改本地 URL。

隧道建立后打开：

```text
http://127.0.0.1:6080/vnc.html
```

点击 `Connect` 后即可操作远端 Chrome。用户要求直接打开页面时，优先使用当前环境提供的浏览器工具打开本地 noVNC URL；不可用时再运行：

```bash
open http://127.0.0.1:6080/vnc.html
```

## 登录与验证

需要人工登录的网站，应让用户在远程桌面的 Chrome 中完成登录。登录后：

1. 打开目标网站，确认页面不再要求登录。
2. 打开用户指定的目标 URL。
3. 按用户要求截图或继续操作。

登录状态保存在远端 Chrome profile。只有使用同一 profile 的浏览器和工具会复用该登录状态；不要声称服务器上的所有工具都会自动获得登录态或绕过网站限制。

## 结束隧道

用户完成远程桌面操作后，停止 SSH 隧道终端 session。确认本机端口已经释放：

```bash
lsof -nP -iTCP:6080 -sTCP:LISTEN
```

不要停止远端 Chrome 或 browser desktop 服务，除非用户明确要求。
