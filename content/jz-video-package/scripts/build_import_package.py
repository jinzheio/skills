#!/usr/bin/env python3
"""从 decisions.json 生成剪映手工导入素材包。

用于剪映 6+ 加密草稿库：无法直接写入可打开草稿时，至少把 B-roll 裁好，
并生成时间轴 CSV、字幕和操作说明。
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_time(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text.endswith("s"):
        return float(text[:-1] or 0)
    if "m" in text:
        minute, rest = text.split("m", 1)
        return float(minute or 0) * 60 + parse_time(rest or "0s")
    return float(text or 0)


def fmt_time(sec: float) -> str:
    minute = int(sec // 60)
    second = sec - minute * 60
    return f"{minute:02d}:{second:05.2f}"


def ffprobe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def make_broll_clip(src: str, dst: Path, duration: float, width: int, height: int) -> None:
    src_duration = ffprobe_duration(src)
    trim = min(src_duration, duration)
    speed = trim / duration
    vf = (
        f"trim=0:{trim},setpts=PTS/{speed},"
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,format=yuv420p"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", src, "-an", "-vf", vf, "-t", str(duration), str(dst)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("decisions")
    parser.add_argument("-o", "--output", default="work/import-package")
    args = parser.parse_args()

    with open(args.decisions, encoding="utf-8") as f:
        data = json.load(f)

    project = data.get("project", {})
    width = int(project.get("width", 1920))
    height = int(project.get("height", 1080))
    out = Path(args.output)
    broll_dir = out / "broll"
    broll_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    broll_count = 0
    for item in data.get("decisions", []):
        kind = item.get("type")
        start = parse_time(item.get("start", item.get("at", 0)))
        if "end" in item:
            end = parse_time(item["end"])
        else:
            end = start + parse_time(item.get("duration", "0s"))
        duration = max(0.01, end - start)
        asset = ""
        note = ""

        if kind == "broll":
            material = item["material"]
            if material.startswith("TODO:") or not os.path.exists(material):
                asset = material
                note = "素材未就绪，需手动补。"
            else:
                broll_count += 1
                safe_time = fmt_time(start).replace(":", "m").replace(".", "_")
                dst = broll_dir / f"{broll_count:02d}_{safe_time}_{Path(material).stem}.mp4"
                make_broll_clip(material, dst, duration, width, height)
                asset = str(dst)
                note = "B-roll 已裁切静音；放在主视频上层，覆盖对应时间段。"
        elif kind == "keyword":
            asset = item.get("text", "")
            note = f"关键词文字；x={item.get('x', 0)}，y={item.get('y', 0)}，size={item.get('size', '')}"
        elif kind == "card":
            asset = " / ".join(item.get("lines", []))
            note = f"文字卡片；逐条出现，间隔 {item.get('line_stagger', '')}"
        elif kind == "host_focus":
            asset = "复制主视频片段"
            note = "复制主视频到上层，加蒙版和放大关键帧；描边、阴影在剪映内补。"
        elif kind in ("overlay", "film_transition"):
            asset = item.get("material", "")
            note = "叠到上层，混合模式设为滤色。"
        else:
            continue

        rows.append({
            "type": kind,
            "start": fmt_time(start),
            "end": fmt_time(end),
            "duration": round(duration, 2),
            "asset_or_text": asset,
            "note": note,
        })

    with open(out / "timeline.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "start", "end", "duration", "asset_or_text", "note"])
        writer.writeheader()
        writer.writerows(rows)

    srt = project.get("srt")
    if srt and os.path.exists(srt):
        shutil.copy2(srt, out / "transcript.srt")

    (out / "README.md").write_text(
        "# 剪映导入包\n\n"
        "当前剪映草稿库是新版加密格式，不能直接写入可打开草稿。\n\n"
        "使用顺序：\n\n"
        "1. 在剪映中新建草稿，导入原口播视频。\n"
        "2. 导入 `transcript.srt` 作为字幕。\n"
        "3. 按 `timeline.csv` 的时间，把 `broll/` 里的片段放到主视频上层。\n"
        "4. 按 `timeline.csv` 添加 keyword/card 文字。\n"
        "5. host_focus 段落复制主视频片段到上层，加蒙版和放大关键帧。\n",
        encoding="utf-8",
    )

    print(f"素材包已生成: {out}")
    print(f"B-roll: {broll_count} 个；时间轴动作: {len(rows)} 条")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"[错误] ffmpeg/ffprobe 执行失败: {e}")
