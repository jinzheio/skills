#!/usr/bin/env python3
"""Analyze a reference video's music: BPM, energy arc, spectrogram.

Usage:
    python3 analyze_audio.py <video-or-audio-file> [--out-dir DIR]

Requires: ffmpeg/ffprobe on PATH, numpy.
Outputs (in --out-dir, default ./audio-analysis):
    ref.wav          extracted mono audio (22.05 kHz)
    spectrogram.png  full-track spectrogram — view it to describe the arc
    analysis.json    machine-readable results
And prints a human summary: duration, BPM candidates, section boundaries.
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HOP_S = 0.01  # onset-envelope hop (10 ms)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out-dir", default="./audio-analysis")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    wav = out / "ref.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", args.input, "-vn", "-ac", "1", "-ar", "22050", str(wav)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-lavfi",
         "showspectrumpic=s=1200x500:legend=1", str(out / "spectrogram.png")])

    with wave.open(str(wav), "rb") as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    dur = len(x) / sr

    # RMS energy envelope
    hop = int(sr * HOP_S)
    win = hop * 2
    nf = (len(x) - win) // hop
    e = np.array([np.sqrt(np.mean(x[i * hop:i * hop + win] ** 2)) for i in range(nf)])

    # Onset envelope: half-wave rectified energy diff
    d = np.diff(e)
    d[d < 0] = 0

    # BPM by autocorrelation over the loudest half of the track
    order = np.argsort(e)[::-1]
    lo = int(np.percentile(order[: len(order) // 2], 5))
    hi = int(np.percentile(order[: len(order) // 2], 95))
    seg = d[max(0, lo):hi] if hi - lo > 500 else d
    seg = seg - seg.mean()
    ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lags = np.arange(30, 101)  # 0.30–1.00 s period → 60–200 BPM
    scored = sorted(lags, key=lambda l: -ac[l])[:5]
    bpm_candidates = [round(60 / (l * HOP_S), 1) for l in scored]
    # prefer 80–140 BPM interpretation (halve/double as needed)
    bpm = bpm_candidates[0]
    while bpm > 140:
        bpm /= 2
    while bpm < 70:
        bpm *= 2

    # Section boundaries: big sustained changes in smoothed energy
    k = int(1.0 / HOP_S)
    smooth = np.convolve(e, np.ones(k) / k, mode="same")
    norm = smooth / max(1e-9, smooth.max())
    thresholds = [0.25, 0.5]
    events = []
    for th in thresholds:
        above = norm > th
        for i in range(1, len(above)):
            if above[i] != above[i - 1]:
                events.append((round(i * HOP_S, 1), f"energy crosses {int(th*100)}% going {'up' if above[i] else 'down'}"))
    # de-duplicate events within 1.5 s
    events.sort()
    dedup = []
    for t, label in events:
        if not dedup or t - dedup[-1][0] > 1.5:
            dedup.append((t, label))

    result = {
        "duration_s": round(dur, 2),
        "bpm_estimate": round(bpm, 1),
        "bpm_candidates": bpm_candidates,
        "sections": [{"t": t, "event": lbl} for t, lbl in dedup],
        "mean_level_note": "run: ffmpeg -i <file> -af volumedetect -f null - for dB levels",
    }
    (out / "analysis.json").write_text(json.dumps(result, indent=2))

    print(f"duration: {dur:.1f}s")
    print(f"BPM estimate: {result['bpm_estimate']} (candidates: {bpm_candidates})")
    print("energy events (approximate section boundaries):")
    for t, lbl in dedup:
        print(f"  {t:6.1f}s  {lbl}")
    print(f"\nwrote {out/'spectrogram.png'} — VIEW IT and describe the arc in words.")
    print(f"wrote {out/'analysis.json'}")


if __name__ == "__main__":
    main()
