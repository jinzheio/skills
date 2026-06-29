---
name: jz-browser-automation
description: 浏览器自动化环境管理。为需要独立浏览器（与用户日常 Chrome 隔离）的自动化任务建立专用 Chrome 实例 + CDP Proxy 连接。触发：建立自动化浏览器、隔离浏览器环境、自动化 Chrome 启动、专用浏览器。当用户说"用我的浏览器"时使用 9222 端口（用户日常 Chrome）；不说明则使用 9333 端口（agent 专用 Chrome）。
---

# 浏览器自动化环境

## 职责

为浏览器自动化任务提供 Chrome + CDP Proxy 连接。支持两种模式：

| 触发条件 | 模式 | 端口 | 用户数据目录 |
|----------|------|------|-------------|
| 用户说"用我的浏览器" | **用户模式** | `9222` | 使用用户默认 Chrome profile 的 DevToolsActivePort |
| 未说明（默认） | **Agent 模式** | `9333` | `$HOME/.chrome-codex-automation`（独立 profile） |

本 skill 不提供 CDP Proxy — 它依赖 `web-access` skill 的 `cdp-proxy.mjs` 和 `check-deps.mjs`。本 skill 只负责：根据需要启动 Chrome、将 Proxy 指向正确端口、验证连接正确。

**为什么默认隔离？**

- 自动化任务可能打开几十个 tab、修改 User-Agent、操作视口 — 这些会污染用户的日常浏览环境。
- 用户日常 Chrome 已有登录的大量网站，自动化操作可能误触发这些网站的交互。
- 隔离后，自动化 Chrome 的登录态、cookie、扩展都与用户无关。

**为什么提供用户模式？**

- 用户已在自己 Chrome 里登录了网站，需要复用现有登录态。
- 无需在自动化 Chrome 里重新登录。

## 模式选择

**每次任务开始时**，根据用户指令判断模式：

1. 用户明确说"用我的浏览器"、"我的 Chrome"、"日常 Chrome"、"登录我的" → **用户模式**，端口 `9222`
2. 用户未说明或说"自动化"、"agent 浏览器"、"专用 Chrome" → **Agent 模式**，端口 `9333`

选好模式后，后续所有步骤使用对应端口和配置。

## 固定配置

### Agent 模式（默认）

| 配置项 | 值 | 说明 |
|--------|-----|------|
| Chrome 应用 | 优先 `Google Chrome for Testing.app` | 与日常 Chrome 在 macOS App Switcher 中区分；找不到时才回退到 `Google Chrome.app` |
| Chrome 调试端口 | `9333` | 专用 Chrome 的 remote-debugging-port |
| Chrome 用户数据目录 | `$HOME/.chrome-codex-automation` | 独立 profile |
| CDP Proxy 端口 | `3456` | web-access proxy 的 HTTP API 端口 |
| Proxy 环境变量 | `CDP_CHROME_PORT=9333` | 强制 proxy 连接专用 Chrome |

### 用户模式

| 配置项 | 值 | 说明 |
|--------|-----|------|
| Chrome 调试端口 | `9222` | 用户日常 Chrome 的 remote-debugging-port |
| Chrome 用户数据目录 | 用户默认 profile | 通过 DevToolsActivePort 自动发现 |
| CDP Proxy 端口 | `3456` | web-access proxy 的 HTTP API 端口 |
| Proxy 环境变量 | `CDP_CHROME_PORT=9222` | 强制 proxy 连接用户 Chrome |

## 启动前自检

每次开始自动化操作前，必须根据当前模式依次执行以下三步，确认环境正确。任何一步失败都必须修复后再继续。

### 步骤 1：检查 Chrome 是否在目标端口运行

**Agent 模式（9333）：**

```bash
curl -s http://127.0.0.1:9333/json/version
```

返回中必须有 `webSocketDebuggerUrl`。如果没有，执行下方「启动专用 Chrome」命令后回到步骤 1 重新验证。

**用户模式（9222）：**

```bash
curl -s http://127.0.0.1:9222/json/version
```

返回中必须有 `webSocketDebuggerUrl`。如果没有，告诉用户：
> 你的 Chrome 需要开启远程调试。请在终端执行：
> ```
> open -na "Google Chrome" --args --remote-debugging-port=9222
> ```
> 这会重启你的 Chrome，保持所有 tab 和登录态不变。

用户确认完成后，回到步骤 1 重新验证。

### 步骤 2：重启 CDP Proxy，强制指向目标端口

旧 proxy 可能连接到错误端口的 Chrome，必须先杀掉再以正确配置重启。

**Agent 模式（9333）：**

```bash
pkill -f 'cdp-proxy.mjs' || true
CDP_CHROME_PORT=9333 \
node ~/.claude/skills/web-access/scripts/check-deps.mjs
```

**用户模式（9222）：**

```bash
pkill -f 'cdp-proxy.mjs' || true
CDP_CHROME_PORT=9222 \
node ~/.claude/skills/web-access/scripts/check-deps.mjs
```

### 步骤 3：确认 Proxy 连接的是正确 Chrome

```bash
curl -s http://127.0.0.1:3456/health
```

返回中的 `chromePort` 必须是当前模式的端口：
- Agent 模式：**`9333`**
- 用户模式：**`9222`**

如果不是预期端口，回到步骤 2，确认环境变量后重新执行。

---

三步全部通过后，可以确认：

- Chrome 在目标端口运行
- CDP Proxy 在 `3456` 端口运行
- Proxy 连接的是正确 Chrome
- 后续所有 CDP 操作通过 `http://localhost:3456` 进行

## 启动专用 Chrome（仅 Agent 模式）

当步骤 1 检测不到 Chrome 在端口 9333 时，优先使用 `Google Chrome for Testing.app`。它和用户日常 Chrome 的名称、图标不同，在 macOS App Switcher 中更容易区分。

先定位 Chrome for Testing：

```bash
CFT_APP="$(find "$HOME/Library/Caches/puppeteer" "$HOME/.cache/puppeteer" \
  -path '*/Google Chrome for Testing.app' \
  -type d 2>/dev/null | head -n 1)"

if [ -z "$CFT_APP" ]; then
  echo "Google Chrome for Testing.app not found"
  echo "Install it with: pnpm dlx @puppeteer/browsers install chrome@stable"
  exit 1
fi
```

找到后执行：

```bash
open -n -g "$CFT_APP" --args \
  --user-data-dir="$HOME/.chrome-codex-automation" \
  --remote-debugging-port=9333 \
  --no-first-run \
  --no-default-browser-check \
  --new-window "about:blank"
```

如果当前机器暂时不能安装 Chrome for Testing，可以临时回退到普通 Chrome：

```bash
open -na "Google Chrome" -g --args \
  --user-data-dir="$HOME/.chrome-codex-automation" \
  --remote-debugging-port=9333 \
  --no-first-run \
  --no-default-browser-check \
  --new-window "about:blank"
```

回退只用于临时处理任务。长期使用时应安装 Chrome for Testing，避免和用户日常 Chrome 在 Alt-Tab / App Switcher 中混淆。

标志说明：

- `-g`：后台启动，不切换到 Chrome 窗口（不打扰用户）
- `--user-data-dir`：独立 profile，与日常 Chrome 完全隔离
- `--remote-debugging-port=9333`：固定调试端口
- `--no-first-run`：跳过首次运行向导
- `--no-default-browser-check`：不检查是否为默认浏览器
- `--new-window "about:blank"`：打开空白窗口

启动后等待 2-3 秒，回到「启动前自检」步骤 1 验证端口可用。

需要登录特定网站时，请用户**只在这个自动化窗口**里登录，不影响日常 Chrome 的登录态。

### 登录 X、微博等账号前检查

Chrome for Testing 可以登录常见网站。它是正常有界面的 Chrome，不是 headless Chrome。账号安全验证通常不只看 User-Agent，还会看新 profile、登录历史、IP、操作频率、设备指纹和自动化行为。

登录 X、微博等账号前，先做一次最小检查：

```bash
curl -s http://127.0.0.1:9333/json/version
```

检查返回中的 `User-Agent`：

- 不应包含 `HeadlessChrome`
- Chrome 主版本应接近日常 Chrome 或当前稳定版
- 如果 User-Agent 明显异常，停止登录，改用普通 Chrome 回退方案或重新安装 Chrome for Testing

账号使用边界：

- 第一次登录由用户手动完成验证码、二次验证和设备确认。
- 不自动执行关注、点赞、转发、私信、发帖、批量搜索、批量打开个人主页等容易触发安全验证的动作。
- 需要账号权限时，默认只做读取页面、截图、辅助填写和用户确认后的单次提交。
- 出现验证码、安全验证或异常登录提示时，停止自动化，让用户手动处理。

## 子 Agent 分派

当主 Agent 将 CDP 任务分派给子 Agent 并行执行时，必须在子 Agent prompt 中写明：

- `必须加载 jz-browser-automation skill 并执行启动前自检`
- **当前模式**（Agent 模式 9333 / 用户模式 9222）
- CDP Proxy 地址：`http://localhost:3456`
- 子 Agent 自己创建 tab、自己关闭 tab，禁止把打开的 tab 留到任务结束后不关
- 禁止子 Agent 未确认 `chromePort` 匹配当前模式就直接开始 CDP 操作

子 Agent 会自动加载本 skill 并执行自检，无需在 prompt 中复制完整步骤。

## 任务结束

CDP 操作全部完成后：

1. 用 `/close` 关闭自己创建的所有 tab
2. 确认无残留：`curl -s http://localhost:3456/targets` 检查只有用户原有的 tab
3. **不关闭 Proxy** — Proxy 保持运行供后续任务使用
4. **Agent 模式**：不关闭专用 Chrome 窗口 — 下一次任务可以复用已有 Chrome，跳过启动步骤
5. **用户模式**：不干扰用户 Chrome
