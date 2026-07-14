---
name: jz-get-wechat-articles
description: "获取微信公众号文章并保存到本地。需要抓取公众号最新文章、补齐历史文章、恢复中断任务、获取文章正文或互动指标、检查状态与历史列表缓存，或汇报新增文章数量时使用。"
---

# 获取微信公众号文章

使用内置脚本获取公众号文章列表、正文和可选的互动指标。

## 默认规则

- 使用 `scripts/get_wechat_articles.py`。
- 在目标项目根目录运行命令。
- 用 `--output-dir` 明确指定目标项目内的输出目录。
- 正文默认用 `--body-source wechat` 直接读取微信文章页。
- 默认开启 `--compact-output`，单次运行目录只保留 `articles/`。
- compact 模式下，每篇文章只保留 `metadata.json`、正文 `.md`，以及可用时的 `stats.json`。不保留 `.html`、`.direct.json` 或 `.article.json`。
- API key 放在 `~/.config/skills/jz-get-wechat-articles/.env`。
- 不要把 API key 写进项目 `.env` 或命令示例。

更改获取范围、正文来源或互动指标选项前，先读 [`references/article-workflow.md`](references/article-workflow.md)。

## 执行规则

- 优先使用内置脚本，不临时拼接 API 调用。
- 日常获取默认用 `--mode latest`。
- 补齐历史文章或恢复中断任务时用 `--mode backfill`。
- 重试时复用同一个 `--output-dir`。
- `backfill` 可以复用缓存的历史列表页和已有状态。
- `latest` 不读历史列表页缓存，必须请求最新列表页。
- `--fetch-metrics` 默认不加。
- 使用 `--fetch-metrics` 时，只请求发布超过 24 小时的文章互动指标。
- `--metrics-from-list-cache-only` 只从本地历史列表缓存读取文章 URL，但仍会请求互动指标 API；必须同时使用 `--fetch-metrics`。
- 复用互动指标缓存，避免重复消耗 API 额度。
- 列表 API 结果写入同一个 SQLite 文件的 `articles` 表。
- 只需要最近几天的文章时，用 `--published-within-days`。
- 只要调用了付费 API，最后汇报初始余额和剩余余额。

## 汇报

任务完成后说明：

1. 新保存文章数
2. 新保存正文数
3. 跳过的已有文章数
4. 列表页来自 API 还是缓存
5. 初始余额和剩余余额
6. 输出目录

## 命令模板

```bash
python3 <skill-dir>/scripts/get_wechat_articles.py \
  --account '目标公众号名称或微信号' \
  --mode latest \
  --published-within-days 3 \
  --body-source wechat \
  --compact-output \
  --delay 1.5 \
  --retry 8 \
  --output-dir ./output/wechat-articles
```

`--compact-output`、`--body-source wechat`、`--mode latest` 和 `--delay 1.5` 都是默认值，模板中显式写出，便于检查本次任务的行为。需要完整调试材料时加 `--no-compact-output`。获取正文和历史补档的细节见 [`references/article-workflow.md`](references/article-workflow.md)。
