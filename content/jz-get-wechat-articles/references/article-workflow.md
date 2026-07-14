# 获取微信公众号文章流程

## 主脚本

- 在目标项目根目录运行命令。
- 使用 `<skill-dir>/scripts/get_wechat_articles.py`。

## API Key

- key 放在 `~/.config/skills/jz-get-wechat-articles/.env`。
- 脚本读取顺序：`--api-key`、环境变量 `JZL_API_KEY` / `JZL_KEY`、skill 配置文件。
- 命令示例里不要写 key。

## 输出目录

- 用 `--output-dir` 明确指定目标项目内的输出目录。
- 同一个公众号复用同一个输出根目录，方便复用状态、历史列表页缓存和互动指标缓存。
- 默认开启 `--compact-output`。单次运行目录只保留 `articles/`。
- 需要排查获取过程时，加 `--no-compact-output` 保留 `manifest.json`、`articles.jsonl`、`stats.jsonl`、`raw_pages/`、`.html` 和原始正文响应。
- 需要直接写入 `--output-dir`、不创建 `<account>_<timestamp>` 目录时，加 `--no-run-dir`。

## 获取模式

### `backfill`

- 用于补齐历史文章。
- 重试时复用同一个 `--output-dir`。
- 可以复用 `.history_pages` 中的历史列表页缓存。
- 缓存页能减少恢复任务时的 `post_history` 花费。

### `latest`

- 用于日常获取，也是默认模式。
- 不读历史列表页缓存。
- 始终请求线上最新列表页。
- 通过状态文件跳过已见文章。

## 公众号定位参数

- `--account`：公众号名称或微信号。
- `--biz-id`：公众号 biz 标识。
- `--source-url`：公众号文章链接或主页链接。
- 至少传一个。多个参数同时存在时，脚本会一并提交给列表 API。

## 时间窗口

- 只需要最近几天时，用 `--published-within-days N`。
- 脚本遇到窗口外的文章后会停止。
- 当前观察到的 `post_history` 是倒序返回，时间窗口在这个前提下工作最好。

## 互动指标

- 用 `--fetch-metrics` 开启，默认关闭。
- 只获取发布超过 24 小时的文章互动指标。
- 指标缓存在公众号输出根目录的 SQLite 文件里，避免重复请求。
- `--metrics-from-list-cache-only` 从本地历史列表页缓存读取文章 URL，跳过列表 API 和正文获取，但仍会请求未缓存的互动指标。
- 优先使用 `read_zan_pro`，不可用时再使用 `article_info`。
- `read_zan_pro` 返回的字段包括 `read`、`zan`、`looking`、`share_num`、`collect_num` 和 `comment_count`。
- 脚本将它们归一化为 `read`、`praise`、`look`、`repost`、`collect` 和 `comment`。
- SQLite 文件名保持为 `<account>.article_stats.sqlite`，兼容已有归档。
- 数据库包含两个表：
  - `articles`：列表 API 元数据，例如 `title`、`digest`、`url`、`post_time`、`cover_url`
  - `article_stats`：归一化互动指标，例如 `read`、`praise`、`look`、`repost`、`collect`、`comment`
- 列表元数据和互动指标放在同一个数据库的不同表里，不合并成稀疏宽表。

## 正文来源

- 正文默认用 `--body-source wechat`。
- 常规补档不要用 `--body-source api`：
  - `article_html` API 每次约 0.3 元。
  - 返回 HTML 经常不如微信移动端页面完整，可能被截断或重排。
  - 约 150 篇文章时，API 路径会多花约 45 元，正文质量通常还更差。
- `wechat` 使用 iPhone 微信 UA，解析 `og:title` / `msg_title`，再提取 `js_content` 正文。
- `--delay` 默认 `1.5` 秒。同一 IP / UA 连续请求太快时，微信可能返回验证页（`环境异常` / `secitptpage/verify`）。
- compact 模式下只保存正文 `.md`，不保留 `.html` 或 `.direct.json`。
- 页面被拦截时，compact 模式保存的 `.md` 会是验证页内容，不是文章。需要确认拦截细节时，用 `--no-compact-output` 重新运行。
- 建议 `--retry 5` 或更高。首次请求偶尔会遇到验证页或短暂网络错误。
- `article_body_fetch_failures` 在 2%–3% 时可以先重试；超过 10% 时，把 `--delay` 翻倍后再试。

## 历史补档

补几个月或几年的历史文章时：

1. 先请求 `post_history`，找到目标日期所在页。结果按倒序返回，`data[].post_time_str` 能看出每页的日期范围。
2. 用 `--start-page` 和 `--end-page` 限定范围，避免为无关页面付费。恢复任务时复用 `.history_pages` 缓存。
3. 注意页码漂移。三个月前在第 16–20 页的文章，之后可能移到更后面的页面。按每天约 3 篇文章计算，90 天大约会漂移 50–60 页。
4. 确认结果前，不要删除本次运行目录 `<account>_<timestamp>`。compact 模式的关键数据在 `articles/`；完整模式还需检查 `articles.jsonl`、`stats.jsonl`、`raw_pages/` 和 `manifest.json`。

## 输出文件

默认 compact 模式下，每篇成功保存的文章通常包含：

- `metadata.json`
- `.md`
- `stats.json`（仅在已获取互动指标时存在）

完整模式（`--no-compact-output`）还会保留：

- `manifest.json`
- `articles.jsonl`
- `stats.jsonl`
- `raw_pages/*.json`
- `.html`
- `.direct.json` 或 `.article.json`

## 汇报

调用 API 后，汇报：

- 初始余额
- 剩余余额
- 列表 API 总花费
- 互动指标 API 总花费
- 数据库文件路径
