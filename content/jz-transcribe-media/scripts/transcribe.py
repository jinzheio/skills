#!/usr/bin/env python3
"""Transcribe audio files using GLM ASR API.

Reads GLM_API_KEY from (in order):
  1. ~/.config/skills/jz-transcribe-media/.env
  2. <skill-root>/.env
  3. environment variable GLM_API_KEY
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

SKILL_NAME = "jz-transcribe-media"
CONFIG_ENV = Path.home() / ".config" / "skills" / SKILL_NAME / ".env"
GLM_API = "https://open.bigmodel.cn/api/paas/v4/audio/transcriptions"
MODEL = "glm-asr-2512"
SEGMENT_SECONDS = 30


def read_env(path: Path) -> dict:
    if not path.exists():
        return {}
    values = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def resolve_api_key(skill_root: Path) -> str:
    # 1. ~/.config/skills/jz-transcribe-media/.env
    if CONFIG_ENV.exists():
        key = read_env(CONFIG_ENV).get("GLM_API_KEY", "")
        if key:
            return key
    # 2. skill dir .env
    skill_env = skill_root / ".env"
    if skill_env.exists():
        key = read_env(skill_env).get("GLM_API_KEY", "")
        if key:
            return key
    # 3. environment
    return os.environ.get("GLM_API_KEY", "")


def get_duration(path: str) -> float:
    """Get audio duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, TypeError):
        raise RuntimeError(f"Cannot probe duration: {result.stderr}")


def ensure_mp3(input_path: str, tmp_dir: str) -> str:
    """Convert to MP3 if needed, return path to MP3 file."""
    ext = Path(input_path).suffix.lower()
    if ext == ".mp3":
        return input_path
    mp3_path = os.path.join(tmp_dir, "input.mp3")
    subprocess.run(
        ["ffmpeg", "-i", input_path, "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k",
         mp3_path, "-y"],
        capture_output=True, text=True, check=True,
    )
    return mp3_path


def split_mp3(mp3_path: str, tmp_dir: str) -> list[str]:
    """Split MP3 into 30-second segments, return sorted list of paths."""
    seg_dir = os.path.join(tmp_dir, "segments")
    os.makedirs(seg_dir, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-i", mp3_path, "-f", "segment",
         "-segment_time", str(SEGMENT_SECONDS), "-c", "copy",
         os.path.join(seg_dir, "seg_%03d.mp3"), "-y"],
        capture_output=True, text=True, check=True,
    )
    return sorted(
        os.path.join(seg_dir, f)
        for f in os.listdir(seg_dir)
        if f.endswith(".mp3")
    )


def transcribe_segment(api_key: str, seg_path: str, index: int, total: int) -> str:
    """Transcribe a single audio segment via GLM ASR API."""
    with open(seg_path, "rb") as fh:
        result = requests.post(
            GLM_API,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": fh},
            data={"model": MODEL, "stream": "false"},
            timeout=120,
        )
    result.raise_for_status()
    data = result.json()
    if "error" in data:
        raise RuntimeError(f"Segment {index}: {data['error'].get('message', data['error'])}")
    text = data.get("text", "")
    return text


def transcribe(input_path: str, output_path: str, api_key: str):
    """Main transcription pipeline."""
    with tempfile.TemporaryDirectory(prefix="transcribe_") as tmp_dir:
        print(f"Preparing audio…")
        mp3_path = ensure_mp3(input_path, tmp_dir)

        duration = get_duration(mp3_path)
        mins, secs = divmod(duration, 60)
        print(f"Duration: {int(mins)}m {secs:.0f}s")

        if duration <= SEGMENT_SECONDS:
            segments = [mp3_path]
        else:
            segments = split_mp3(mp3_path, tmp_dir)
        total = len(segments)
        last_err = None

        print(f"Transcribing {total} segment(s) via GLM ASR…")
        full_text = ""
        for i, seg in enumerate(segments, start=1):
            size_kb = os.path.getsize(seg) / 1024
            print(f"  [{i}/{total}] {os.path.basename(seg)} ({size_kb:.0f}KB)…", end=" ", flush=True)
            try:
                text = transcribe_segment(api_key, seg, i, total)
                full_text += text
                print(f"{len(text)} chars")
            except Exception as exc:
                last_err = exc
                full_text += f"\n[segment {i} error: {exc}]\n"
                print(f"ERROR: {exc}")

        # Clean leading blank lines
        full_text = full_text.lstrip("\n")

        if output_path:
            Path(output_path).write_text(full_text)
            print(f"\nSaved: {output_path}")
        else:
            print(f"\n--- Transcript ---\n{full_text}")
        if last_err:
            print("\nWarning: some segments failed.", file=sys.stderr)
    return full_text


def main():
    skill_root = Path(__file__).resolve().parent.parent
    api_key = resolve_api_key(skill_root)
    if not api_key:
        print("Error: GLM_API_KEY not found.", file=sys.stderr)
        print(f"  Tried: {CONFIG_ENV}", file=sys.stderr)
        print(f"  Tried: {skill_root / '.env'}", file=sys.stderr)
        print("  Tried: $GLM_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Transcribe audio to text via GLM ASR")
    parser.add_argument("input", help="Audio file path")
    parser.add_argument("-o", "--output", help="Output text file path", default="")
    parser.add_argument("--language", default="zh", help="Language hint (informational only)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Default output: same basename as input + .txt
    output = args.output
    if not output:
        output = str(Path(args.input).with_suffix(".txt"))

    transcribe(args.input, output, api_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
