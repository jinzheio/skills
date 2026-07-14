---
name: jz-launch-chrome
description: 启动本机两类 Chrome：用户日常 Chrome（带已登录 profile）和 Agent 专用 Chrome（隔离 profile，固定 CDP 端口 9333）。触发：打开我的 Chrome、启动带 profile 的 Chrome、启动 agent chrome、恢复 Chrome profile、区分日常 Chrome 和自动化 Chrome。
---

# Chrome 启动器

## 职责

用同一个 `Google Chrome.app` 分别启动两套浏览器环境：

- **日常 Chrome**：使用默认 Chrome 数据目录，打开用户指定 profile。默认 profile 是 `Profile 6`，可通过参数或 `JZ_DAILY_CHROME_PROFILE` 覆盖。
- **Agent Chrome**：使用 `$HOME/.chrome-codex-automation`，固定 `--remote-debugging-port=9333`，与日常 Chrome 的登录态、cookie、扩展隔离。

不要把日常 Chrome 当作自动化浏览器。需要 CDP 自动化时，使用 Agent Chrome。

## 快速命令

```bash
<skill-dir>/scripts/launch-chrome.sh daily
```

```bash
<skill-dir>/scripts/launch-chrome.sh agent
```

```bash
<skill-dir>/scripts/launch-chrome.sh status
```

打开其它日常 profile：

```bash
<skill-dir>/scripts/launch-chrome.sh daily "Profile 1"
```

或：

```bash
JZ_DAILY_CHROME_PROFILE="Profile 1" <skill-dir>/scripts/launch-chrome.sh daily
```

## 规则

### 用户说“打开我的 Chrome”

执行：

```bash
<skill-dir>/scripts/launch-chrome.sh daily
```

这会打开带用户日常 profile 的 Chrome。不要给它加 `--user-data-dir`，否则会变成另一个数据目录。

### 用户说“打开 Agent Chrome”

执行：

```bash
<skill-dir>/scripts/launch-chrome.sh agent
```

这会打开隔离 profile，并使用 `9333` 端口。

### 用户要排查当前 Chrome 状态

执行：

```bash
<skill-dir>/scripts/launch-chrome.sh status
```

重点看：

- 主进程参数里是否有 `--user-data-dir=$HOME/.chrome-codex-automation`
- `9333` 是否被 Agent Chrome 监听
- 默认 Chrome 数据目录的 `SingletonLock` 指向哪个进程

## 注意

Chrome 136 之后，默认用户数据目录不再可靠支持 `--remote-debugging-port`。日常 Chrome 用来人工浏览；Agent Chrome 用来 CDP 自动化。
