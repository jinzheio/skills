---
name: jz-video-transcript
description: 从 YouTube 或 X 视频中提取字幕/转录，生成英文、中文和双语 Markdown 文件。当用户需要视频字幕、转录、视频列表中的 URL 或视频的中文翻译时使用。处理 YouTube 自动字幕、X VTT 字幕、重复滚动字幕文本，以及中文机器翻译。
---

# 视频字幕提取

当需要从一个或多个 YouTube 或 X 视频 URL 获取字幕、转录或中文翻译时使用此技能。

## 默认工作流

1. 将输入标准化为每行一个 URL。
2. 运行 `scripts/video_transcript.py`，指定输出目录。
3. 优先使用源平台的英文 VTT 字幕。
4. 生成：
   - `transcript.en.md`
   - `transcript.zh.md`
   - `transcript.bilingual.md`
   - `meta.json`
   - 源 `.en.vtt`
   - 根目录 `INDEX.md`
5. 当 `--output-format kb`（默认）时，同时写一份干净的知识库副本到 `raw/clippings/youtube/<channel-slug>/<title-slug>/`，包含 `transcript.md`、`transcript.zh.md` 和 `meta.json`——与 `raw/clippings/wechat/` 的目录惯例一致。
6. 运行后，验证生成的转录文件数量与目标视频数量一致。

## 命令

单个视频：

```bash
uv run python <skill-dir>/scripts/video_transcript.py \
  "https://www.youtube.com/watch?v=<video-id>" \
  --output-dir ./video-transcripts
```

X 视频：

```bash
uv run python <skill-dir>/scripts/video_transcript.py \
  "https://x.com/<user>/status/<post-id>" \
  --output-dir ./video-transcripts
```

从文本文件批量处理：

```bash
uv run python <skill-dir>/scripts/video_transcript.py \
  --input-file ./video-urls.txt \
  --output-dir ./video-transcripts
```

仅英文：

```bash
uv run python <skill-dir>/scripts/video_transcript.py \
  --input-file ./video-urls.txt \
  --output-dir ./video-transcripts \
  --engine none
```

## 依赖

- `yt-dlp` 必须在 `PATH` 中。
- Python 3.10+。
- 获取英文字幕需要网络访问源视频平台。
- 仅当请求中文翻译时需要访问 `translate.googleapis.com`。

如果缺少 `yt-dlp`，先安装或使其在环境中可用，再让用户重试。

## 输入规则

- 接受完整 YouTube URL、`youtu.be` URL、Shorts URL、X 状态 URL 或原始 YouTube 视频 ID。
- 对于 YouTube 频道或播放列表，先使用 `yt-dlp --flat-playlist` 创建 URL 列表，然后将该文件通过 `--input-file` 传入。
- 对于日期窗口，先单独收集视频 URL 列表；此脚本仅处理给定的 URL。
- X 视频必须通过 `yt-dlp` 暴露英文 VTT 字幕轨道。如果没有字幕轨道，将该 URL 报告为失败。

## 输出结构

```text
video-transcripts/
├── INDEX.md
└── <channel-slug>/
    └── <date>__<video-id>__<title-slug>/
        ├── meta.json
        ├── source.en.vtt
        ├── transcript.en.md
        ├── transcript.zh.md
        └── transcript.bilingual.md
```

使用 `--output-format kb`（默认）时，额外在以下路径生成副本：

```text
raw/clippings/youtube/<channel-slug>/<title-slug>/
├── meta.json
├── transcript.md
└── transcript.zh.md
```

使用 `--output-format plain` 跳过知识库副本。

## 重要实现细节

- YouTube 自动 VTT 经常在每个字幕帧中重复前面的单词。不要直接翻译原始 VTT 行。
- X VTT 可能包含 `<X-word-ms>` 时间标签。使用脚本解析器，因为它会剥离标记并保留可读文本。
- 使用脚本解析器，因为在可用的情况下它会仅保留增量字幕文本，并删除重复的滚动字幕行。
- 从 YouTube 翻译端点获取中文字幕可能返回 HTTP 429。将其视为正常情况。使用英文字幕加脚本翻译，而不是无限重试。
- 机器翻译对于阅读和搜索足够好用。用于发布时，手动审核重要名称、产品术语和不通顺的句子。

## 验证

运行后检查：

```bash
find ./video-transcripts -name 'transcript.zh.md' | wc -l
find ./video-transcripts -name 'transcript.en.md' | wc -l
sed -n '1,40p' ./video-transcripts/INDEX.md
```

汇报：

1. 目标视频数量。
2. 生成的英文转录数量。
3. 生成的中文转录数量。
4. 输出目录。
5. 所有失败的 URL。

## 失败处理

- YouTube 中文字幕 `HTTP Error 429`：继续使用英文 VTT 加翻译。
- 缺少英文字幕：将该视频 URL 报告为失败；不要编造转录文本。
- X 登录墙或媒体提取失败：将该 URL 报告为失败，附带 `yt-dlp` 错误信息。
- 翻译超时：重新运行同一命令。脚本可以安全地覆盖已有的视频目录。
- 机器翻译质量差：保留原始英文转录，标记中文文件需要人工审核。
