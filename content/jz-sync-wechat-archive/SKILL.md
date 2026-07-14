---
name: jz-sync-wechat-archive
description: "抓取和更新微信公众号文章归档。需要运行内置 `wechat_archive.py` 脚本执行 `full` 或 `latest` 同步、恢复中断的归档任务、抓取文章数据、检查状态文件或缓存历史页、汇报某个公众号新增文章数量时使用。"
---

# 微信公众号文章归档同步

当任务涉及抓取或更新微信公众号文章归档时使用这个 skill。

## 默认规则

- 主脚本是 `scripts/wechat_archive.py`。
- 在目标项目根目录运行命令。
- `--output-dir` 必须明确写在目标项目内。
- 正文默认用 `--body-source direct`。
- 默认开启 `--compact-output`，单次运行目录只保留 `articles/`。
- compact 模式下每篇文章只保留 `metadata.json`、正文 `.md`、有统计时的 `stats.json`；不保留 `.html`、`.direct.json` 或 `.article.json`。
- API key 放在 `~/.config/skills/jz-sync-wechat-archive/.env`。
- 不要把 API key 写进项目 `.env` 或命令示例。

改抓取行为或给同步命令前，先读 [`references/archive-workflow.md`](references/archive-workflow.md)。

## 执行规则

- 优先使用本地脚本，不临时拼 API 调用。
- 日常同步用 `--mode latest`。
- 历史补档或恢复中断任务才用 `--mode full`。
- 重试时复用同一个 `--output-dir`。
- `full` 可以复用缓存的 `history_pages` 和已有状态。
- `latest` 不读页面缓存，必须请求最新列表页。
- `--fetch-stats` 默认不加。
- 使用 `--fetch-stats` 时，只请求发布时间超过 24 小时的文章数据。
- 复用数据缓存，避免重复消耗 API 额度。
- 列表 API 结果写进同一个 SQLite 文件的 `articles` 表。
- 只需要最近几天时，用 `--published-within-days`。
- 只要用了 API，最后汇报初始余额和剩余余额。

## 汇报

同步完成后说明：

1. 新保存文章数
2. 新保存正文数
3. 跳过的已有文章数
4. 列表页来自 API 还是缓存
5. 初始余额和剩余余额
6. 输出目录

## 命令模板

```bash
python3 "$HOME/.agents/skills/jz-sync-wechat-archive/scripts/wechat_archive.py" \
  --name '目标公众号名称或微信号' \
  --mode latest \
  --fetch-stats \
  --published-within-days 3 \
  --body-source direct \
  --compact-output \
  --delay 1.5 \
  --retry 8 \
  --output-dir ./output/wechat-archive
```

`--compact-output` 默认开启，命令里写出来只是为了提醒输出形态。需要完整调试材料时加 `--no-compact-output`。`--body-source direct` 是默认选择。`--delay 1.5` 用来降低触发微信验证页的概率。正文抓取和补档细节见 [`references/archive-workflow.md`](references/archive-workflow.md)。
