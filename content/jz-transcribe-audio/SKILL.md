---
name: jz-transcribe-audio
description: 使用 GLM ASR API 将音频和视频文件转写为中文文本。当用户想将语音备忘录、会议录音、采访或视频转换为文字时使用。支持常见格式（m4a、mp3、wav、mp4、mov），通过 ffmpeg 自动转换。内部将文件拆分为 30 秒片段，可处理任意长度的文件。
---

# 音频转写

将音频或视频通过 [GLM-ASR-2512](https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-asr-2512) 转为中文文本。

## 快速开始

```bash
python3 <skill-dir>/scripts/transcribe.py ~/Downloads/录音.m4a
```

输出默认写在输入文件旁边，文件名为 `<输入文件名>.txt`。可通过 `-o` 指定输出路径：

```bash
python3 <skill-dir>/scripts/transcribe.py ~/Downloads/录音.m4a -o ~/Downloads/转录.txt
```

## 工作原理

1. 如果输入不是 MP3，ffmpeg 将其转换为 MP3（128 kbps）。
2. 超过 30 秒的音频被拆分为 30 秒片段。
3. 每个片段 POST 到 GLM ASR 端点（`glm-asr-2512`）。
4. 结果拼接后写入输出文件。

## 支持的格式

通过 ffmpeg 自动转换支持：m4a、wav、mp3、mp4、mov、flac、ogg、webm、aac 以及大多数常见音视频容器格式。

## 凭证

API key 查找顺序：

1. `~/.config/skills/jz-transcribe-audio/.env` ← 推荐
2. `<skill-root>/.env`
3. `GLM_API_KEY` 环境变量

每个来源均为简单的 `GLM_API_KEY=<key>` 行。

## 费用

GLM-ASR-2512 价格为 **¥0.06 / 分钟**。一段 14 分钟的录音大约花费 ¥0.85。

## 限制

- 最大文件大小：25 MB
- 最大片段时长：30 秒（脚本自动拆分更长的文件）
- 支持的片段格式：wav、mp3

## 注意事项

- glm-asr-2512 是较新的模型（2025 年 12 月）。如果 API 返回 "unknown model" 错误，请查阅[官方文档](https://docs.bigmodel.cn/api-reference/模型-API/语音转文本)获取当前模型名称。
- 30 秒拆分使用 ffmpeg segment copy，因此边界可能偶尔落在单词中间——相邻片段通常能覆盖断点。
- 极短的片段（几秒静音）可能产生空输出或乱码。
