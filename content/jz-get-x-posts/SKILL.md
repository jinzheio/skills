---
name: jz-get-x-posts
description: 按 `username` 或 `userId` 获取指定数量的最新 X 帖子。用于用户说“抓某个 X 账号最近 20/50/100 条帖子”“按 userId 拉 X 帖子”“保存成 Markdown/JSON”“检查这个账号最近发了什么”时。默认使用 Twittr RapidAPI，先取 user timeline，不够时再用 search 补齐。
---

# 获取 X 帖子

当任务是按 `username` 或 `userId` 抓取某个 X 账号最近若干条帖子时使用这个 skill。

## 默认规则

- 主脚本是 `scripts/fetch_x.py`。
- 优先读取本机全局 skill 配置目录中的 `.env`。
- 如果全局 `.env` 不存在，再回退到 skill 目录本地 `.env`。
- `~/.config/skills/jz-get-x-posts/users.json` 维护 `username` 和 `userId` 的对应关系。运行前先查这个文件；API 成功解析新账号后要及时更新它，避免重复请求账号解析接口。
- 不要把 API key 写进仓库 `.env`、命令示例或最终回复。
- 默认保留 API 返回的转推文本；如果用户明确说“只要原创帖”，再加 `--exclude-retweets`。
- 默认输出 JSON 到标准输出；需要落文件时显式传 `--output-dir`。

## 凭据

### 配置位置

脚本按以下顺序读取 `.env`（先找到的先生效）：

1. **全局配置**（优先）：`~/.config/skills/jz-get-x-posts/.env`
2. **本地回退**：`{skill_dir}/.env`
3. **环境变量**：当前 shell 的 `os.environ`

> 把 key 写在全局配置里，所有项目都能共享，不用在每个仓库里重复放。

### 支持的变量名

每个变量都可以放单个 key；`TWITTER241_API_KEYS` 也可以放逗号分隔的多个 key。

- `TWITTR_RAPIDAPI_KEY`
- `RAPIDAPI_KEY`
- `X_API_KEY`
- `TWITTER241_API_KEYS`

脚本会按顺序尝试 key；如果某个 key 返回 `409`、`429`、`403` 或其它请求错误，自动换下一个 key。只有所有 key 都失败时才中止。

## 执行规则

- 用户给 `username` 时，先转成 `userId`，再抓 timeline。
- 用户只给 `userId` 时，先查用户资料把 `username` 补出来。
- 转换前先查 `~/.config/skills/jz-get-x-posts/users.json`；缓存命中时不请求账号解析接口。
- 主路径是 `/user/{userId}/tweets` 分页。
- 如果 timeline 不足目标数量，且已经知道 `username`，再用 `/search?query=from:<username>&type=Latest` 分页补齐。
- 合并两条结果后按发布时间倒序去重，保留最近 N 条。
- 返回前说明一共请求了多少次 API、失败请求次数、是否更新了账号映射，以及最终拿到多少条唯一帖子。

## 常用命令

按 `username` 抓最近 100 条，并写入 Markdown 和 JSON：

```bash
uv run python ./scripts/fetch_x.py \
  --username <x-username> \
  --count 100 \
  --output-dir ./output/x
```

按 `userId` 抓最近 50 条，只输出 JSON 到标准输出：

```bash
uv run python ./scripts/fetch_x.py \
  --user-id 1382389316245069826 \
  --count 50
```

只保留原创帖：

```bash
uv run python ./scripts/fetch_x.py \
  --username <x-username> \
  --count 100 \
  --exclude-retweets \
  --output-dir ./output/x
```

## 输出

如果传了 `--output-dir`，脚本会写两个文件：

- `<handle>-x-recent-<count>-<date>.json`
- `<handle>-x-recent-<count>-<date>.md`

JSON 适合后续程序处理。Markdown 适合人工阅读和归档。

## 汇报

运行后至少要说明：

1. 入口是 `username` 还是 `userId`
2. 目标条数和最终条数
3. 是否用了 search 补齐
4. API 请求次数和失败请求次数
5. `~/.config/skills/jz-get-x-posts/users.json` 是否新增或更新映射
6. 输出目录或输出文件名
