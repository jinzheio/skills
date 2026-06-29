---
name: jz-douyin-transcript
description: Transcribe Douyin videos to Markdown. Use for one Douyin video URL or for a Douyin user/profile batch. Writes transcripts under raw/clippings/douyin/<channel>/ with sync-state.json progress to avoid repeated downloads. Defaults to latest 30 videos and skips videos longer than 5 minutes.
---

# Douyin Transcript

Use this skill to transcribe Douyin oral videos into Markdown files.

## What It Does

- Supports a single video URL.
- Supports a Douyin profile/user URL batch.
- Defaults to latest 30 videos for profile batch.
- Skips videos longer than 5 minutes by default.
- Saves progress in `raw/clippings/douyin/<channel>/sync-state.json`.
- Writes one Markdown file per usable transcript.

## Command

Single video:

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --url "https://www.douyin.com/video/<video-id>" \
  --channel <channel-name>
```

Batch from a profile:

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --profile-url "https://www.douyin.com/user/<sec_uid>" \
  --channel <channel-name>
```

Continue until 10 more usable transcripts are produced:

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --profile-url "https://www.douyin.com/user/<sec_uid>" \
  --channel <channel-name> \
  --add-usable 10
```

Use an existing URL list:

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --input-file urls.txt \
  --channel <channel-name>
```

## Output

```text
raw/clippings/douyin/<channel-name>/
├── sync-state.json
├── urls.latest.txt
└── <video-id>.md
```

Each Markdown file contains:

- title
- channel
- Douyin URL
- transcript text

## Requirements

- Python 3.10+
- `requests`
- `ffmpeg` and `ffprobe` on `PATH`
- GLM API key configured for `jz-transcribe-audio`
- Node.js and Playwright for profile collection
- For profile collection, an existing logged-in Chrome/Chrome for Testing with remote debugging is recommended:

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --profile-url "https://www.douyin.com/user/<sec_uid>" \
  --channel <channel-name> \
  --cdp http://127.0.0.1:9333
```

If CDP is unavailable, pass `--input-file` with known video URLs.

## Notes

- Existing successful Markdown files are skipped.
- Failed items are skipped by default on later runs. Use `--retry-failed` to retry them.
- Videos longer than `--max-duration-seconds` are marked failed and skipped. Default: `300`.
- Tiny or segment-error transcripts do not count toward the usable target.

## Verification

After running:

```bash
python3 <skill-dir>/scripts/douyin_transcript.py \
  --channel <channel-name> \
  --status
```

Report:

- output directory
- usable transcript count
- failed count
- skipped long videos
