#!/usr/bin/env python3
import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


TAG_RE = re.compile(r"<[^>]+>")
TIMESTAMP_RE = re.compile(
    r"(?P<start>\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(?P<end>\d{2}:\d{2}:\d{2}\.\d{3})"
)
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
ZH_SUB_LANGS = ("zh-Hans", "zh-CN", "zh")
PROTECTED_TERMS = (
    "Claude Code",
    "LLM",
    "LLMs",
    "token",
    "tokens",
)
COMMON_TERM_FIXES = (
    (re.compile(r"法学硕士"), "LLM"),
    (re.compile(r"克劳德[·・]?代码"), "Claude Code"),
    (re.compile(r"代币"), "token"),
)


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=True)


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if VIDEO_ID_RE.match(value):
        return f"https://www.youtube.com/watch?v={value}"
    return value


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "video"


def clean_text(text: str) -> str:
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def hms(timestamp: str) -> str:
    return timestamp.split(".", 1)[0]


def load_urls(args: argparse.Namespace) -> list[str]:
    urls = [normalize_url(item) for item in args.urls if item.strip()]
    if args.input_file:
        for line in args.input_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(normalize_url(line.split()[0]))
    seen = set()
    unique = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def get_metadata(url: str) -> dict:
    result = run(["yt-dlp", "--skip-download", "--dump-single-json", "--no-warnings", url])
    data = json.loads(result.stdout)
    return {
        "id": data.get("id") or "",
        "title": data.get("title") or data.get("fulltitle") or "Untitled",
        "channel": data.get("channel") or data.get("uploader") or "youtube",
        "channel_id": data.get("channel_id") or data.get("uploader_id") or "",
        "upload_date": format_upload_date(data.get("upload_date")),
        "duration": data.get("duration_string") or seconds_to_hms(data.get("duration")),
        "url": data.get("webpage_url") or url,
    }


def format_upload_date(value: str | None) -> str:
    if not value or len(value) != 8:
        return "unknown-date"
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def seconds_to_hms(value) -> str:
    if value is None:
        return ""
    value = int(value)
    h, rem = divmod(value, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def download_vtt(url: str, video_dir: Path, video_id: str, sub_langs: str, source_name: str) -> Path | None:
    for old in video_dir.glob(f"{video_id}.*.vtt"):
        old.unlink(missing_ok=True)
    run(
        [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs",
            sub_langs,
            "--sub-format",
            "vtt",
            "--no-warnings",
            "-o",
            f"{video_id}.%(ext)s",
            url,
        ],
        cwd=video_dir,
    )
    matches = sorted(video_dir.glob(f"{video_id}.*.vtt"))
    if not matches:
        return None
    source = video_dir / source_name
    source.write_text(matches[0].read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    if matches[0] != source:
        matches[0].unlink(missing_ok=True)
    return source


def download_english_vtt(url: str, video_dir: Path, video_id: str) -> Path:
    path = download_vtt(url, video_dir, video_id, "en", "source.en.vtt")
    if path is None:
        raise FileNotFoundError(f"English VTT not found for {url}")
    return path


def download_chinese_vtt(url: str, video_dir: Path, video_id: str) -> tuple[Path, str] | tuple[None, None]:
    for lang in ZH_SUB_LANGS:
        try:
            path = download_vtt(url, video_dir, video_id, lang, f"source.{lang}.vtt")
        except subprocess.CalledProcessError:
            continue
        if path is not None:
            return path, lang
    return None, None


def parse_vtt(path: Path) -> list[dict]:
    cues = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    i = 0
    while i < len(lines):
        match = TIMESTAMP_RE.search(lines[i])
        if not match:
            i += 1
            continue
        start = match.group("start")
        end = match.group("end")
        i += 1
        text_lines = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i])
            i += 1
        incremental = [
            line for line in text_lines if "<c>" in line or re.search(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", line)
        ]
        text = clean_text(" ".join(incremental or text_lines))
        if text:
            cues.append({"start": hms(start), "end": hms(end), "text": text})
        i += 1

    filtered = []
    for cue in cues:
        if filtered and filtered[-1]["text"] == cue["text"]:
            filtered[-1]["end"] = cue["end"]
            continue
        filtered.append(cue)
    return filtered


def timestamp_seconds(timestamp: str | None) -> int:
    if not timestamp:
        return 0
    parts = timestamp.split(":")
    if len(parts) != 3:
        return 0
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


def make_paragraphs(cues: list[dict], max_words: int) -> list[dict]:
    paragraphs = []
    bucket = []
    word_count = 0
    start = None
    end = None
    for cue in cues:
        if start is None:
            start = cue["start"]
        bucket.append(cue["text"])
        word_count += len(cue["text"].split())
        end = cue["end"]
        if word_count >= max_words or (word_count >= 35 and cue["text"].endswith((".", "?", "!"))):
            paragraphs.append({"start": start, "end": end, "text": " ".join(bucket)})
            bucket = []
            word_count = 0
            start = None
    if bucket:
        paragraphs.append({"start": start, "end": end, "text": " ".join(bucket)})
    return paragraphs


def align_cues_to_paragraphs(cues: list[dict], paragraphs: list[dict]) -> list[str]:
    aligned = []
    cue_index = 0
    for paragraph in paragraphs:
        start = timestamp_seconds(paragraph["start"])
        end = timestamp_seconds(paragraph["end"])
        parts = []
        seen = set()
        while cue_index < len(cues) and timestamp_seconds(cues[cue_index]["end"]) < start:
            cue_index += 1
        scan_index = cue_index
        while scan_index < len(cues):
            cue = cues[scan_index]
            cue_start = timestamp_seconds(cue["start"])
            cue_end = timestamp_seconds(cue["end"])
            if cue_start > end:
                break
            if cue_end >= start:
                text = postprocess_terms(cue["text"])
                if text and text not in seen:
                    parts.append(text)
                    seen.add(text)
            scan_index += 1
        aligned.append(clean_joined_zh("".join(parts) if parts else ""))
    return aligned


def clean_joined_zh(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([，。！？、：；）])", r"\1", text)
    text = re.sub(r"([（])\s+", r"\1", text)
    return text


def protect_terms(text: str) -> tuple[str, dict[str, str]]:
    replacements = {}
    protected = text
    for index, term in enumerate(sorted(PROTECTED_TERMS, key=len, reverse=True)):
        placeholder = f"ZXQTERM{index:03d}ZXQ"
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)

        def replace(match: re.Match) -> str:
            replacements[placeholder] = match.group(0)
            return placeholder

        protected = pattern.sub(replace, protected)
    return protected, replacements


def restore_terms(text: str, replacements: dict[str, str]) -> str:
    restored = text
    for placeholder, original in replacements.items():
        restored = re.sub(re.escape(placeholder), original, restored, flags=re.IGNORECASE)
        restored = re.sub(r"\s*".join(re.escape(part) for part in placeholder), original, restored, flags=re.IGNORECASE)
    return postprocess_terms(restored)


def postprocess_terms(text: str) -> str:
    fixed = text
    for pattern, replacement in COMMON_TERM_FIXES:
        fixed = pattern.sub(replacement, fixed)
    return fixed


class GoogleTranslator:
    def __init__(self, sleep_seconds: float = 0.1) -> None:
        self.base_url = "https://translate.googleapis.com/translate_a/single"
        self.separator = "###SEG###"
        self.sleep_seconds = sleep_seconds

    def translate_many(self, texts: list[str]) -> list[str]:
        protected_items = [protect_terms(text) for text in texts]
        protected_texts = [item[0] for item in protected_items]
        batches = []
        current = []
        current_len = 0
        for text in protected_texts:
            proposed = current_len + len(text) + len(self.separator) + 2
            if current and proposed > 3500:
                batches.append(current)
                current = []
                current_len = 0
            current.append(text)
            current_len += len(text) + len(self.separator) + 2
        if current:
            batches.append(current)

        results = []
        for batch in batches:
            results.extend(self._translate_batch(batch))
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
        return [
            restore_terms(translated, replacements)
            for translated, (_, replacements) in zip(results, protected_items)
        ]

    def translate_one(self, text: str) -> str:
        return self.translate_many([text])[0]

    def _translate_batch(self, texts: list[str]) -> list[str]:
        joined = f"\n{self.separator}\n".join(texts)
        last_error = None
        for _ in range(3):
            try:
                translated = self._request(joined)
                parts = [part.strip() for part in translated.split(self.separator)]
                if len(parts) != len(texts):
                    if len(texts) == 1:
                        return [translated.strip()]
                    mid = len(texts) // 2
                    return self._translate_batch(texts[:mid]) + self._translate_batch(texts[mid:])
                return parts
            except Exception as exc:
                last_error = exc
                time.sleep(1)
        if len(texts) > 1:
            mid = len(texts) // 2
            return self._translate_batch(texts[:mid]) + self._translate_batch(texts[mid:])
        raise RuntimeError(f"translation failed: {last_error}") from last_error

    def _request(self, text: str) -> str:
        query = urllib.parse.urlencode(
            {
                "client": "gtx",
                "sl": "en",
                "tl": "zh-CN",
                "dt": "t",
                "q": text,
            }
        )
        request = urllib.request.Request(
            f"{self.base_url}?{query}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
        return "".join(part[0] for part in data[0] if part and part[0])


def write_markdown_files(
    video_dir: Path, meta: dict, paragraphs: list[dict], zh_texts: list[str] | None,
    kb_dir: Path | None = None,
) -> None:
    frontmatter = [
        "---",
        f'title: "{escape_yaml(meta["title"])}"',
        f'channel: "{escape_yaml(meta["channel"])}"',
        f'date: "{meta["upload_date"]}"',
        f'duration: "{meta["duration"]}"',
        f'url: "{meta["url"]}"',
        "---",
        "",
    ]
    en_lines = frontmatter + [f"# {meta['title']}", "", f"Source: {meta['url']}", ""]
    for paragraph in paragraphs:
        en_lines.append(f"[{paragraph['start']} -> {paragraph['end']}] {paragraph['text']}")
        en_lines.append("")
    (video_dir / "transcript.en.md").write_text("\n".join(en_lines), encoding="utf-8")

    if zh_texts is None:
        if kb_dir is not None:
            kb_dir.mkdir(parents=True, exist_ok=True)
            (kb_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            (kb_dir / "transcript.md").write_text("\n".join(en_lines), encoding="utf-8")
        return

    zh_lines = frontmatter + [f"# {meta['title']}", "", f"原视频：{meta['url']}", ""]
    bilingual_lines = frontmatter + [f"# {meta['title']}", "", f"Source: {meta['url']}", ""]
    for paragraph, zh in zip(paragraphs, zh_texts):
        stamp = f"[{paragraph['start']} -> {paragraph['end']}]"
        zh_lines.append(f"{stamp} {zh}")
        zh_lines.append("")
        bilingual_lines.append(f"{stamp}")
        bilingual_lines.append("")
        bilingual_lines.append(paragraph["text"])
        bilingual_lines.append("")
        bilingual_lines.append(zh)
        bilingual_lines.append("")
    (video_dir / "transcript.zh.md").write_text("\n".join(zh_lines), encoding="utf-8")
    (video_dir / "transcript.bilingual.md").write_text("\n".join(bilingual_lines), encoding="utf-8")

    if kb_dir is not None:
        kb_dir.mkdir(parents=True, exist_ok=True)
        (kb_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (kb_dir / "transcript.md").write_text("\n".join(en_lines), encoding="utf-8")
        (kb_dir / "transcript.zh.md").write_text("\n".join(zh_lines), encoding="utf-8")


def escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def process_video(
    url: str,
    output_dir: Path,
    args: argparse.Namespace,
    translator: GoogleTranslator | None,
    kb_root: Path | None = None,
) -> dict:
    meta = get_metadata(url)
    channel_slug = slugify(meta["channel"])
    title_slug = slugify(meta["title"])[:120]
    video_dir = output_dir / channel_slug / f'{meta["upload_date"]}__{meta["id"]}__{title_slug}'
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    vtt_path = download_english_vtt(url, video_dir, meta["id"])
    cues = parse_vtt(vtt_path)
    if not cues:
        raise RuntimeError(f"No caption text parsed for {url}")
    paragraphs = make_paragraphs(cues, args.max_words)
    zh_texts = None
    zh_source = "none"
    zh_vtt_path, zh_lang = download_chinese_vtt(url, video_dir, meta["id"])
    if zh_vtt_path is not None:
        zh_cues = parse_vtt(zh_vtt_path)
        if zh_cues:
            zh_texts = align_cues_to_paragraphs(zh_cues, paragraphs)
            zh_source = zh_lang or "youtube-zh"
    if translator is not None:
        missing_indexes = [index for index, text in enumerate(zh_texts or []) if not text]
        if zh_texts is None:
            zh_texts = translator.translate_many([paragraph["text"] for paragraph in paragraphs])
            zh_source = "google"
        elif missing_indexes:
            translated_missing = translator.translate_many([paragraphs[index]["text"] for index in missing_indexes])
            for index, translated in zip(missing_indexes, translated_missing):
                zh_texts[index] = translated
            zh_source = f"{zh_source}+google"

    kb_dir = None
    if kb_root is not None:
        kb_dir = kb_root / channel_slug / title_slug

    write_markdown_files(video_dir, meta, paragraphs, zh_texts, kb_dir=kb_dir)
    return {
        "id": meta["id"],
        "title": meta["title"],
        "date": meta["upload_date"],
        "url": meta["url"],
        "paragraphs": len(paragraphs),
        "path": str(video_dir.relative_to(output_dir)),
        "zh": zh_texts is not None,
        "zh_source": zh_source,
    }


def write_index(output_dir: Path, records: list[dict], failures: list[dict]) -> None:
    index = {record["id"]: record for record in records}
    (output_dir / ".index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Video Transcripts",
        "",
        f"Completed: {len(records)}",
        f"Failed: {len(failures)}",
        "",
        "| Date | Title | URL | English | Chinese | Bilingual | Paragraphs |",
        "|---|---|---|---|---|---|---|",
    ]
    for record in records:
        path = record["path"]
        title = record["title"].replace("|", "\\|")
        zh_link = f"[zh]({path}/transcript.zh.md)" if record["zh"] else ""
        bilingual_link = f"[bilingual]({path}/transcript.bilingual.md)" if record["zh"] else ""
        lines.append(
            f"| {record['date']} | {title} | {record['url']} | [en]({path}/transcript.en.md) | {zh_link} | {bilingual_link} | {record['paragraphs']} |"
        )
    if failures:
        lines.extend(["", "## Failures", ""])
        for failure in failures:
            lines.append(f"- {failure['url']}: {failure['error']}")
    (output_dir / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch video English captions and optional Chinese translations.")
    parser.add_argument("urls", nargs="*", help="YouTube URLs, X status URLs, or raw YouTube video IDs")
    parser.add_argument("--input-file", type=Path, help="Text file with one video URL or raw YouTube video ID per line")
    parser.add_argument("--output-dir", type=Path, default=Path("video-transcripts"))
    parser.add_argument("--output-format", choices=["kb", "plain"], default="kb",
                        help="'kb' also produces a clip in raw/clippings/youtube/<channel>/<slug>/; 'plain' only outputs to --output-dir")
    parser.add_argument("--kb-root", type=Path, default=Path("raw/clippings/youtube"),
                        help="Knowledge base root when --output-format=kb (default: raw/clippings/youtube)")
    parser.add_argument("--engine", choices=["google", "none"], default="google", help="Chinese translation engine")
    parser.add_argument("--max-words", type=int, default=60, help="Approximate English words per paragraph")
    parser.add_argument("--sleep", type=float, default=0.1, help="Sleep seconds between translation batches")
    args = parser.parse_args()

    if shutil.which("yt-dlp") is None:
        print("ERROR: yt-dlp is required but was not found on PATH.", file=sys.stderr)
        return 2

    urls = load_urls(args)
    if not urls:
        print("ERROR: provide at least one video URL, raw YouTube video ID, or --input-file.", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    translator = GoogleTranslator(args.sleep) if args.engine == "google" else None
    records = []
    failures = []
    for index, url in enumerate(urls, start=1):
        try:
            record = process_video(
                url, args.output_dir, args, translator,
                kb_root=args.kb_root if args.output_format == "kb" else None,
            )
            records.append(record)
            print(f"OK {index}/{len(urls)} {record['id']} paragraphs={record['paragraphs']} {record['path']}", flush=True)
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})
            print(f"FAIL {index}/{len(urls)} {url}: {exc}", file=sys.stderr, flush=True)
    write_index(args.output_dir, records, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
