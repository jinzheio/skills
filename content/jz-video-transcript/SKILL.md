---
name: jz-video-transcript
description: Fetch video subtitles/transcripts from YouTube or X videos and create English, Chinese, and bilingual Markdown files. Use when the user wants video subtitles, transcripts, captions, URLs from a video list, or Chinese translations of videos. Handles YouTube auto captions, X VTT captions, repeated rolling caption text, and machine translation for Chinese output.
---

# Video Transcript

Use this skill when the task is to get video subtitles, transcripts, or Chinese translations from one or more YouTube or X video URLs.

## Default Workflow

1. Normalize the input into one URL per line.
2. Run `scripts/video_transcript.py` with an explicit output directory.
3. Prefer English VTT captions from the source platform.
4. Generate:
   - `transcript.en.md`
   - `transcript.zh.md`
   - `transcript.bilingual.md`
   - `meta.json`
   - source `.en.vtt`
   - root `INDEX.md`
5. When `--output-format kb` (default), also write a clean knowledge-base copy to `raw/clippings/youtube/<channel-slug>/<title-slug>/` containing `transcript.md`, `transcript.zh.md`, and `meta.json` — mirroring the `raw/clippings/wechat/` convention.
6. After running, verify the number of generated transcript files equals the number of target videos.

## Command

Single video:

```bash
uv run python <skill-dir>/scripts/video_transcript.py \
  "https://www.youtube.com/watch?v=<video-id>" \
  --output-dir ./video-transcripts
```

X video:

```bash
uv run python <skill-dir>/scripts/video_transcript.py \
  "https://x.com/<user>/status/<post-id>" \
  --output-dir ./video-transcripts
```

Multiple videos from a text file:

```bash
uv run python <skill-dir>/scripts/video_transcript.py \
  --input-file ./video-urls.txt \
  --output-dir ./video-transcripts
```

English only:

```bash
uv run python <skill-dir>/scripts/video_transcript.py \
  --input-file ./video-urls.txt \
  --output-dir ./video-transcripts \
  --engine none
```

## Requirements

- `yt-dlp` must be available on `PATH`.
- Python 3.10+.
- Network access to the source video platform for English captions.
- Network access to `translate.googleapis.com` only when Chinese translation is requested.

If `yt-dlp` is missing, install or make it available in the current environment before asking the user to retry.

## Input Rules

- Accept full YouTube URLs, `youtu.be` URLs, Shorts URLs, X status URLs, or raw YouTube video IDs.
- For a YouTube channel or playlist, first use `yt-dlp --flat-playlist` to create a URL list, then pass that file with `--input-file`.
- For date windows, collect the video URL list separately first; this script only processes the URLs it is given.
- X videos must expose an English VTT caption track through `yt-dlp`. If no caption track exists, report the URL as failed.

## Output Layout

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

With `--output-format kb` (default), an additional copy is placed:

```text
raw/clippings/youtube/<channel-slug>/<title-slug>/
├── meta.json
├── transcript.md
└── transcript.zh.md
```

Use `--output-format plain` to skip the knowledge-base copy.

## Important Implementation Details

- YouTube auto VTT often repeats previous words on each caption frame. Do not translate raw VTT lines directly.
- X VTT can contain `<X-word-ms>` timing tags. Use the script parser because it strips markup and keeps readable text.
- Use the script parser because it keeps only incremental caption text where available and removes repeated rolling caption lines.
- Chinese captions from YouTube translation endpoints may return HTTP 429. Treat that as normal. Use English captions plus script translation instead of retrying indefinitely.
- Machine translation is good enough for reading and search. For publishing, manually review important names, product terms, and awkward sentences.

## Verification

After running, check:

```bash
find ./video-transcripts -name 'transcript.zh.md' | wc -l
find ./video-transcripts -name 'transcript.en.md' | wc -l
sed -n '1,40p' ./video-transcripts/INDEX.md
```

Report:

1. Target video count.
2. Generated English transcript count.
3. Generated Chinese transcript count.
4. Output directory.
5. Any failed URLs.

## Failure Handling

- `HTTP Error 429` from YouTube Chinese subtitles: continue with English VTT plus translation.
- Missing English captions: report the video URL as failed; do not invent transcript text.
- X login wall or media extraction failure: report the URL as failed and include the `yt-dlp` error.
- Translation timeout: rerun the same command. Existing completed video directories may be overwritten safely by the script.
- Bad machine translation: keep the raw English transcript and note that the Chinese file needs review.
