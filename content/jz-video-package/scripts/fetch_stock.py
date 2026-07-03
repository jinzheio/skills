#!/usr/bin/env python3
"""从 Pexels（fallback Pixabay）搜索并下载免版权视频素材。

用法:
    python3 fetch_stock.py "man thinking silhouette cinematic" -n 3 -o work/materials/

API key 放 ~/.config/skills/jz-video-package/.env:
    PEXELS_API_KEY=...
    PIXABAY_API_KEY=...
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ENV_PATH = os.path.expanduser("~/.config/skills/jz-video-package/.env")


def load_env() -> dict:
    env = {}
    if os.path.exists(ENV_PATH):
        for line in open(ENV_PATH, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def http_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def download(url: str, path: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
        while chunk := r.read(1 << 16):
            f.write(chunk)


def pick_file(video_files: list) -> str | None:
    """选 1080p 左右的文件，太大浪费、太小画质差。"""
    ranked = sorted(video_files, key=lambda v: abs((v.get("height") or 0) - 1080))
    return ranked[0]["link"] if ranked else None


def search_pexels(query: str, n: int, key: str) -> list[tuple[str, str]]:
    data = http_json(
        f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page={n}&orientation=portrait",
        {"Authorization": key})
    out = []
    for v in data.get("videos", []):
        link = pick_file(v.get("video_files", []))
        if link:
            out.append((f"pexels-{v['id']}", link))
    return out


def search_pixabay(query: str, n: int, key: str) -> list[tuple[str, str]]:
    data = http_json(
        f"https://pixabay.com/api/videos/?key={key}&q={urllib.parse.quote(query)}&per_page={max(n, 3)}")
    out = []
    for v in data.get("hits", [])[:n]:
        files = v.get("videos", {})
        best = files.get("large") or files.get("medium") or files.get("small")
        if best and best.get("url"):
            out.append((f"pixabay-{v['id']}", best["url"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="英文关键词，加 cinematic/moody 过滤图库味")
    ap.add_argument("-n", type=int, default=3)
    ap.add_argument("-o", "--output", default="work/materials")
    args = ap.parse_args()

    env = load_env()
    results = []
    if env.get("PEXELS_API_KEY"):
        try:
            results = search_pexels(args.query, args.n, env["PEXELS_API_KEY"])
        except Exception as e:
            print(f"[警告] Pexels 搜索失败: {e}", file=sys.stderr)
    if not results and env.get("PIXABAY_API_KEY"):
        try:
            results = search_pixabay(args.query, args.n, env["PIXABAY_API_KEY"])
        except Exception as e:
            print(f"[警告] Pixabay 搜索失败: {e}", file=sys.stderr)
    if not results:
        sys.exit(f"[错误] 无结果。检查 {ENV_PATH} 里的 API key，或换关键词。")

    os.makedirs(args.output, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.query.lower()).strip("-")[:40]
    for name, url in results:
        path = os.path.join(args.output, f"{slug}-{name}.mp4")
        print(f"下载 {url} → {path}")
        download(url, path)
    print(f"✅ 已下载 {len(results)} 个素材到 {args.output}（逐个抽帧检查色调后再用）")


if __name__ == "__main__":
    main()
