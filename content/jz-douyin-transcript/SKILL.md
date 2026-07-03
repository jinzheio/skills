---
name: jz-douyin-transcript
description: 将抖音视频转写为 Markdown。支持单个视频 URL 或抖音用户/主页批量转写。转录文件写入 raw/clippings/douyin/<channel>/，通过 sync-state.json 记录进度以避免重复下载。默认获取最近 30 个视频，跳过超过 5 分钟的视频。
---

# 抖音视频转写

将抖音口播视频转写为 Markdown 文件。

## 功能

- 支持单个视频 URL。
- 支持抖音主页/用户 URL 批量转写。
- 批量转写默认获取最近 30 个视频。
- 默认跳过超过 5 分钟的视频。
- 进度保存在 `raw/clippings/douyin/<channel>/sync-state.json`。
- 每条有效转录输出一个 Markdown 文件。

## 命令

单个视频：

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --url "https://www.douyin.com/video/<video-id>" \
  --channel <channel-name>
```

从主页批量获取：

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --profile-url "https://www.douyin.com/user/<sec_uid>" \
  --channel <channel-name>
```

继续处理直到再产出 10 条有效转录：

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --profile-url "https://www.douyin.com/user/<sec_uid>" \
  --channel <channel-name> \
  --add-usable 10
```

仅转写每个视频的前一分钟：

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --profile-url "https://www.douyin.com/user/<sec_uid>" \
  --channel <channel-name> \
  --latest 10 \
  --max-duration-seconds 0 \
  --clip-seconds 60
```

使用已有的 URL 列表：

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --input-file urls.txt \
  --channel <channel-name>
```

## 输出

```text
raw/clippings/douyin/<channel-name>/
├── sync-state.json
├── urls.latest.txt
└── <video-id>.md
```

每个 Markdown 文件包含：

- 标题
- 频道
- 抖音链接
- 转录文本

## 依赖

- Python 3.10+
- `requests`
- `ffmpeg` 和 `ffprobe` 在 `PATH` 中
- 已为 `jz-transcribe-audio` 配置好 GLM API key
- 收集主页视频需要 Node.js 和 Playwright
- 收集主页视频时，建议使用已登录的 Chrome/Chrome for Testing 并开启远程调试：

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --profile-url "https://www.douyin.com/user/<sec_uid>" \
  --channel <channel-name> \
  --cdp http://127.0.0.1:9333
```

如果 CDP 不可用，可传 `--input-file` 指定已知的视频 URL。

## 注意事项

- 已有成功转写的 Markdown 文件会被跳过。
- 失败的条目默认在后续运行时跳过。使用 `--retry-failed` 重试。
- 超过 `--max-duration-seconds` 的视频会被标记为失败并跳过。默认值：`300`。
- 过短或片段错误的转录不计入有效目标。

## 验证

运行后：

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --channel <channel-name> \
  --status
```

汇报：

- 输出目录
- 有效转录数量
- 失败数量
- 跳过的长视频数量
