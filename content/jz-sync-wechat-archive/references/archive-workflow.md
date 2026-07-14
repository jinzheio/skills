# 微信公众号文章归档流程

## 主脚本

- 在目标项目根目录运行命令。
- 使用 `$HOME/.agents/skills/jz-sync-wechat-archive/scripts/wechat_archive.py`。

## API Key

- key 放在 `~/.config/skills/jz-sync-wechat-archive/.env`。
- 脚本读取顺序：`--api-key`、环境变量 `JZL_API_KEY` / `JZL_KEY`、skill 配置文件。
- 命令示例里不要写 key。

## 输出目录

- `--output-dir` 必须明确写在目标项目内。
- 同一个公众号复用同一个输出根目录，方便复用状态、页面缓存和数据缓存。
- 默认开启 `--compact-output`。单次运行目录只保留 `articles/`。
- 需要排查抓取过程时，加 `--no-compact-output` 保留 `manifest.json`、`articles.jsonl`、`stats.jsonl`、`raw_pages/`、`.html` 和原始正文响应。

## 模式规则

### `full`

- 用于历史补档。
- 重试时复用同一个 `--output-dir`。
- `full` 可以复用缓存的 `history_pages`。
- 缓存页能减少恢复任务时的 `post_history` 花费。

### `latest`

- 用于日常同步。
- 不读页面缓存。
- 始终请求线上最新列表页。
- 通过状态文件跳过已见文章。

## 时间窗口

- 只需要最近几天时，用 `--published-within-days N`。
- 脚本遇到窗口外的文章后会停止。
- 当前观察到的 `post_history` 是倒序返回，时间窗口在这个前提下工作最好。

## 文章数据

- 用 `--fetch-stats` 开启。
- 默认不开启。
- 只抓取发布时间超过 24 小时的文章数据。
- 数据缓存在公众号输出根目录下的 SQLite 文件里，避免重复请求。
- 优先用 `read_zan_pro`。
- 当前 `read_zan_pro` 明确返回：
  - `read`
  - `zan`
  - `looking`
  - `share_num`
  - `collect_num`
  - `comment_count`
- 归一化为：
  - `read`
  - `praise`
  - `look`
  - `repost`
  - `collect`
  - `comment`
- 如果 `read_zan_pro` 不可用，再用 `article_info`。
- SQLite 文件名是 `<account>.article_stats.sqlite`。
- 里面有两个表：
  - `articles`：列表 API 元数据，如 `title`、`digest`、`url`、`post_time`、`cover_url`
  - `article_stats`：归一化数据，如 `read`、`praise`、`look`、`repost`、`collect`、`comment`
- 列表元数据和文章数据放在同一个数据库的不同表里，不合并成稀疏宽表。

## 正文抓取

- 正文默认用 `--body-source direct`。
- 常规补档不要用 `--body-source api`：
  - `article_html` API 每次约 0.3 元。
  - 返回 HTML 经常不如微信移动端页面完整，可能被截断或重排。
  - 约 150 篇文章时，API 路径比 `direct` 多花约 45 元，正文质量还更差。
- `direct` 会使用 iPhone 微信 UA，解析 `og:title` / `msg_title`，再提取 `js_content` 正文。
- `direct` 的 `--delay` 至少设为 `1.0`，默认建议 `1.5`。同一 IP / UA 连续请求太快时，微信可能返回验证页（`环境异常` / `secitptpage/verify`）。
- compact 模式下只保存正文 `.md`，不保留 `.html` 或 `.direct.json`。
- 页面被拦截时，compact 模式下保存的 `.md` 会是验证页内容，不是文章；需要确认拦截细节时，用 `--no-compact-output` 重新跑。
- `direct` 建议 `--retry 5` 或更高。首次请求偶尔会遇到验证页或短暂网络错误。
- `article_body_fetch_failures` 在 2-3% 属于正常范围。超过 10% 时，把 `--delay` 翻倍后重试。

## 历史补档

补几个月或几年的历史文章时，按下面做：

1. 先用 `curl` 请求 `post_history`，找到目标日期所在页。`post_history` 按倒序返回，`data[].post_time_str` 能看出每页的日期范围。
   ```bash
   set -a; source ~/.config/skills/jz-sync-wechat-archive/.env; set +a
   curl -sS -X POST 'https://www.dajiala.com/fbmain/monitor/v3/post_history' \
     -H 'Content-Type: application/json' \
     -d "{\"name\":\"公众号名\",\"page\":N,\"key\":\"$JZL_API_KEY\"}" \
     -o /tmp/pageN.json
   ```
2. 用 `--start-page` 和 `--end-page` 限定范围，避免为不需要的页面付费。恢复任务时复用缓存的 `history_pages`。
3. 注意页码漂移。三个月前在第 16-20 页的文章，现在可能已经移到第 70-80 页。按每天约 3 篇文章计算，90 天大约会漂移 50-60 页。
4. 不要在确认前删除本次运行目录，例如 `<account>_<timestamp>`。compact 模式下关键数据都在这个目录的 `articles/` 里；完整模式下还要按需要处理 `articles.jsonl`、`stats.jsonl`、`raw_pages/` 和 `manifest.json`。

## 输出文件

默认 compact 模式下，每篇成功保存的文章通常包含：

- `metadata.json`
- `.md`
- `stats.json`（仅在已成功获取统计时存在）

完整模式（`--no-compact-output`）还会保留：

- `manifest.json`
- `articles.jsonl`
- `stats.jsonl`
- `raw_pages/*.json`
- `.html`
- `.direct.json` 或 `.article.json`

## 汇报

- 使用 API 后，汇报：
  - 初始余额
  - 剩余余额
  - 列表 API 总花费
  - stats API 总花费
  - 数据库文件路径
