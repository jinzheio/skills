#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
ROUTER_DATA_RE = re.compile(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", re.S)
DOUYIN_VIDEO_RE = re.compile(r"/(?:video|note|gallery)/(\d{10,25})")


def skill_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def sibling_transcribe_script() -> Path:
    return skill_dir().parent / "jz-transcribe-media" / "scripts" / "transcribe.py"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    return value.strip("-") or "douyin"


def load_state(path: Path, channel: str) -> dict[str, Any]:
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
    else:
        state = {"created_at": now(), "channel": channel, "items": {}, "runs": []}
    state.setdefault("channel", channel)
    state.setdefault("items", {})
    state.setdefault("runs", [])
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(cmd: list[str], *, timeout: int | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        timeout=timeout,
        text=True,
        capture_output=capture,
    )


def normalize_video_url(value: str) -> str:
    value = value.strip()
    match = DOUYIN_VIDEO_RE.search(value)
    if match:
        return f"https://www.douyin.com/video/{match.group(1)}"
    if value.isdigit():
        return f"https://www.douyin.com/video/{value}"
    return value


def video_id_from_url(url: str) -> str:
    match = DOUYIN_VIDEO_RE.search(url)
    if not match:
        raise ValueError(f"cannot extract video id: {url}")
    return match.group(1)


def read_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(normalize_video_url(line.split()[0]))
    return urls


def collect_profile_urls(profile_url: str, cdp: str, limit: int) -> list[dict[str, str]]:
    script = skill_dir() / "scripts" / "_collect_profile_tmp.mjs"
    raise_if_missing_node()
    result = run(
        [
            "node",
            str(script),
            "--profile-url",
            profile_url,
            "--cdp",
            cdp,
            "--limit",
            str(limit),
        ],
        timeout=900,
        capture=True,
    )
    return json.loads(result.stdout)


def raise_if_missing_node() -> None:
    if not shutil.which("node"):
        raise RuntimeError("node is required for profile collection")


def fetch_video_info(video_id: str) -> dict[str, Any]:
    share_url = f"https://www.iesdouyin.com/share/video/{video_id}"
    response = requests.get(share_url, headers={"User-Agent": MOBILE_UA}, timeout=30)
    response.raise_for_status()
    match = ROUTER_DATA_RE.search(response.text)
    if not match:
        raise RuntimeError(f"_ROUTER_DATA not found for {video_id}")
    router_data = json.loads(match.group(1).strip())
    item = (((router_data.get("loaderData") or {}).get("video_(id)/page") or {}).get("videoInfoRes") or {}).get("item_list", [{}])[0]
    play = ((item.get("video") or {}).get("play_addr") or {}).get("url_list") or []
    if not play:
        raise RuntimeError(f"no play URL for {video_id}")
    return {
        "id": video_id,
        "title": item.get("desc") or "",
        "url": f"https://www.douyin.com/video/{video_id}",
        "download_url": str(play[0]).replace("playwm", "play", 1),
    }


def download_file(url: str, dest: Path) -> None:
    with requests.get(
        url,
        headers={"User-Agent": MOBILE_UA, "Referer": "https://www.douyin.com/"},
        timeout=300,
        stream=True,
    ) as response:
        response.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)


def media_duration_seconds(path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture=True,
    )
    return float(result.stdout.strip() or 0)


def extract_mono_mp3(media_path: Path, audio_path: Path, clip_seconds: int = 0) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(media_path),
        "-vn",
        "-ac",
        "1",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "128k",
    ]
    if clip_seconds > 0:
        cmd.extend(["-t", str(clip_seconds)])
    cmd.append(str(audio_path))
    run(cmd, timeout=180)


def write_markdown(path: Path, item: dict[str, Any], channel: str, transcript: str) -> None:
    title = (item.get("title") or item["id"]).replace('"', '\\"')
    duration = item.get("duration_seconds")
    clip = item.get("clip_seconds")
    duration_line = f"duration_seconds: {duration}\n" if duration is not None else ""
    clip_line = f"clip_seconds: {clip}\n" if clip else ""
    body = f"""---
title: "{title}"
channel: "{channel}"
source: "{item['url']}"
video_id: "{item['id']}"
type: douyin-transcript
{duration_line}{clip_line}transcript_scope: "{'first ' + str(clip) + ' seconds' if clip else 'full video'}"
---

# {item.get('title') or item['id']}

Source: {item['url']}

## Transcript

{transcript.strip()}
"""
    path.write_text(body, encoding="utf-8")


def usable_markdown(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 160:
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "[segment " in text or "## Transcript" not in text:
        return False
    transcript = text.split("## Transcript", 1)[1].strip()
    return len(transcript) >= 80


def transcribe_video(item: dict[str, Any], channel: str, out_dir: Path, max_duration: int, keep_audio: bool, clip_seconds: int) -> Path:
    video_id = item["id"]
    md_path = out_dir / f"{video_id}.md"
    if usable_markdown(md_path):
        return md_path
    if md_path.exists():
        md_path.unlink()

    info = fetch_video_info(video_id)
    item.update({k: v for k, v in info.items() if v})
    with tempfile.TemporaryDirectory(prefix=f"douyin_{video_id}_") as tmp_raw:
        tmp = Path(tmp_raw)
        media_path = tmp / f"{video_id}.mp4"
        audio_path = tmp / f"{video_id}.mono.mp3"
        txt_path = tmp / f"{video_id}.txt"
        download_file(item["download_url"], media_path)
        duration = media_duration_seconds(media_path)
        item["duration_seconds"] = round(duration, 3)
        if max_duration > 0 and duration > max_duration:
            raise RuntimeError(f"duration {duration:.0f}s exceeds max_duration_seconds={max_duration}")
        if clip_seconds > 0:
            item["clip_seconds"] = clip_seconds
        extract_mono_mp3(media_path, audio_path, clip_seconds)
        transcript_duration = min(duration, clip_seconds) if clip_seconds > 0 else duration
        run([sys.executable, str(sibling_transcribe_script()), str(audio_path), "-o", str(txt_path)], timeout=max(180, int(transcript_duration * 8)))
        transcript = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        if "[segment " in transcript:
            raise RuntimeError("transcript contains failed segments")
        if len(transcript) < 80:
            raise RuntimeError("transcript too short or empty")
        if keep_audio:
            audio_dir = out_dir / "_audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(audio_path, audio_dir / f"{video_id}.mono.mp3")
        write_markdown(md_path, item, channel, transcript)
    return md_path


def add_item(state: dict[str, Any], item: dict[str, Any], source_set: str) -> str:
    key = f"video:{item['id']}"
    existing = state["items"].setdefault(
        key,
        {
            "id": item["id"],
            "url": item["url"],
            "title": item.get("title", ""),
            "created_at": now(),
            "transcription": {"status": "pending"},
            "source_sets": [],
        },
    )
    existing.update({k: v for k, v in item.items() if v})
    if source_set not in existing.setdefault("source_sets", []):
        existing["source_sets"].append(source_set)
    return key


def count_usable(state: dict[str, Any], out_dir: Path, keys: list[str]) -> int:
    count = 0
    for key in keys:
        item = state["items"].get(key)
        if item and usable_markdown(out_dir / f"{item['id']}.md"):
            count += 1
    return count


def print_status(state: dict[str, Any], out_dir: Path) -> None:
    counts: dict[str, int] = {}
    usable = 0
    for item in state.get("items", {}).values():
        status = (item.get("transcription") or {}).get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
        if usable_markdown(out_dir / f"{item['id']}.md"):
            usable += 1
    print(json.dumps({"items": len(state.get("items", {})), "status": counts, "usable": usable, "output_dir": str(out_dir)}, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="append", default=[])
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--profile-url")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--raw-root", type=Path, default=Path("raw/clippings/douyin"))
    parser.add_argument("--latest", type=int, default=30)
    parser.add_argument("--add-usable", type=int, default=0)
    parser.add_argument("--max-duration-seconds", type=int, default=300)
    parser.add_argument("--clip-seconds", type=int, default=0)
    parser.add_argument("--cdp", default="http://127.0.0.1:9333")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--keep-audio", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    channel = slugify(args.channel)
    out_dir = args.raw_root / channel
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "sync-state.json"
    state = load_state(state_path, channel)

    if args.status:
        print_status(state, out_dir)
        return 0

    source_keys: list[str] = []
    urls = [normalize_video_url(url) for url in args.url]
    if args.input_file:
        urls.extend(read_urls(args.input_file))
    for url in urls:
        video_id = video_id_from_url(url)
        source_keys.append(add_item(state, {"id": video_id, "url": url}, "manual"))

    if args.profile_url:
        profile_items = collect_profile_urls(args.profile_url, args.cdp, args.latest)
        for item in profile_items[: args.latest]:
            source_keys.append(add_item(state, item, "latest"))
        (out_dir / "urls.latest.txt").write_text(
            "\n".join(state["items"][key]["url"] for key in source_keys if key in state["items"]) + "\n",
            encoding="utf-8",
        )

    if not source_keys:
        source_keys = list(state.get("items", {}).keys())

    baseline_usable = count_usable(state, out_dir, source_keys)
    target = baseline_usable + args.add_usable if args.add_usable else args.latest
    run_record = {
        "started_at": now(),
        "target_usable": target,
        "max_duration_seconds": args.max_duration_seconds,
        "clip_seconds": args.clip_seconds,
    }
    state["runs"].append(run_record)
    save_state(state_path, state)

    for key in source_keys:
        if count_usable(state, out_dir, source_keys) >= target:
            break
        item = state["items"].get(key)
        if not item:
            continue
        tr = item.setdefault("transcription", {"status": "pending"})
        if tr.get("status") == "failed" and not args.retry_failed:
            continue
        if usable_markdown(out_dir / f"{item['id']}.md"):
            tr["status"] = "success"
            save_state(state_path, state)
            continue
        tr.update({"status": "running", "updated_at": now()})
        save_state(state_path, state)
        try:
            md_path = transcribe_video(item, channel, out_dir, args.max_duration_seconds, args.keep_audio, args.clip_seconds)
            tr.update({"status": "success", "output_path": str(md_path), "updated_at": now()})
            print(f"OK {item['id']} -> {md_path}")
        except Exception as exc:
            tr.pop("output_path", None)
            tr.update({"status": "failed", "error": str(exc), "updated_at": now()})
            print(f"FAIL {item['id']}: {exc}", file=sys.stderr)
        save_state(state_path, state)

    run_record["completed_at"] = now()
    run_record["usable"] = count_usable(state, out_dir, source_keys)
    save_state(state_path, state)
    print_status(state, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
