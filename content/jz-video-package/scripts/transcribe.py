#!/usr/bin/env python3
"""口播视频转录，输出带词级时间戳的 transcript.json 和 .srt。

用法:
    python3 transcribe.py <视频或音频> -o work/transcript.json [--model small] [--lang zh]

依赖: ffmpeg + faster-whisper (pip install faster-whisper)。
已有 srt 时无需本脚本，直接在 decisions.json 里引用即可。
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile


def extract_audio(src: str) -> str:
    wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav],
                   check=True, capture_output=True)
    return wav


def fmt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default="transcript.json")
    ap.add_argument("--model", default="small", help="faster-whisper 模型 (tiny/small/medium/large-v3)")
    ap.add_argument("--lang", default="zh")
    args = ap.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("[错误] 未安装 faster-whisper: pip install faster-whisper")

    wav = extract_audio(args.input)
    try:
        model = WhisperModel(args.model, device="auto", compute_type="auto")
        segments, info = model.transcribe(wav, language=args.lang, word_timestamps=True,
                                          vad_filter=True)
        out_segments = []
        for seg in segments:
            out_segments.append({
                "start": round(seg.start, 2), "end": round(seg.end, 2),
                "text": seg.text.strip(),
                "words": [{"w": w.word, "start": round(w.start, 2), "end": round(w.end, 2)}
                          for w in (seg.words or [])],
            })
    finally:
        os.unlink(wav)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"language": info.language, "duration": round(info.duration, 2),
                   "segments": out_segments}, f, ensure_ascii=False, indent=1)

    srt_path = os.path.splitext(args.output)[0] + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(out_segments, 1):
            f.write(f"{i}\n{fmt_ts(seg['start'])} --> {fmt_ts(seg['end'])}\n{seg['text']}\n\n")

    print(f"✅ {len(out_segments)} 段 → {args.output} / {srt_path}")


if __name__ == "__main__":
    main()
