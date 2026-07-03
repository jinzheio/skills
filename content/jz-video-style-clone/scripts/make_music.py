#!/usr/bin/env python3
"""Synthesize an upbeat electronic promo bed (stdlib + numpy only).

Edit the PARAMETERS block to match (a) the reference's BPM/energy arc and
(b) YOUR video's scene timeline — the breakdown should land on the
price/credibility scene and the outro pad on the logo scene.

Structure produced:
    0 .. FULL_START      intro: muted kick+hats, filtered pad swell
    FULL_START..BREAK    full groove: 4/4 kick, offbeat hats, bass 8ths,
                         chord stabs, arp
    BREAK .. OUTRO       breakdown: sparse kick, claps, big pads
    OUTRO .. DUR         soft pads + sparse plucks, fade to zero

Usage:  python3 make_music.py [-o theme.wav]
Then:   ffmpeg -y -i theme.wav -af "treble=g=-2.5:f=9000,volume=-2.5dB" \
            -c:a aac -b:a 192k promo-theme.m4a
"""
import argparse

import numpy as np
import wave

# ----------------------------- PARAMETERS -----------------------------
SR = 44100
BPM = 100.0            # from analyze_audio.py
DUR = 39.1             # total seconds; >= your video duration
BEAT = 60.0 / BPM
BAR = 4 * BEAT

FULL_START = 2 * BAR   # groove opens up (bars are easiest to reason in)
BREAK_START = 11 * BAR # drums thin out — align to price/credibility scene
OUTRO_START = 13 * BAR # pads only — align to logo/outro scene

# chords as MIDI note lists + matching bass roots; default: warm-neutral
# Fmaj7 – Am7 – C – G6 loop. Transpose by adding/subtracting semitones.
CHORDS = [
    [53, 57, 60, 64],  # Fmaj7
    [57, 60, 64, 67],  # Am7
    [48, 55, 60, 64],  # C
    [55, 59, 62, 64],  # G6
]
BASS = [41, 45, 36, 43]
# ----------------------------------------------------------------------

rng = np.random.default_rng(7)
N = int(DUR * SR)
L = np.zeros(N)
R = np.zeros(N)


def hz(midi):
    return 440 * 2 ** ((midi - 69) / 12)


def add(sig, t0, pan=0.0, gain=1.0):
    i0 = int(t0 * SR)
    i1 = min(i0 + len(sig), N)
    if i0 >= N:
        return
    seg = sig[: i1 - i0] * gain
    L[i0:i1] += seg * np.sqrt(0.5 * (1 - pan)) * 1.414
    R[i0:i1] += seg * np.sqrt(0.5 * (1 + pan)) * 1.414


def env_exp(n, decay):
    return np.exp(-np.arange(n) / SR / decay)


def kick(vel=1.0):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 40 + 90 * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.11)
    out = body.copy()
    click = rng.standard_normal(int(0.004 * SR)) * 0.4
    out[: len(click)] += click
    return np.tanh(out * 2.2) * 0.9 * vel


def hat(open_=False, vel=1.0):
    n = int((0.3 if open_ else 0.05) * SR)
    hp = np.diff(np.diff(rng.standard_normal(n), prepend=0.0), prepend=0.0)
    hp /= max(1e-9, np.max(np.abs(hp)))
    return hp * env_exp(n, 0.09 if open_ else 0.012) * 0.32 * vel


def clap(vel=1.0):
    n = int(0.25 * SR)
    noise = rng.standard_normal(n)
    bp = noise - np.convolve(noise, np.ones(8) / 8, mode="same")
    e = env_exp(n, 0.05)
    for dt in (0.012, 0.024):
        i = int(dt * SR)
        e[i:] += 0.7 * env_exp(n - i, 0.045)
    return bp * e * 0.5 * vel


def saw(freq, n, detune=0.004):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for d in (1 - detune, 1.0, 1 + detune):
        out += 2 * ((t * freq * d) % 1.0) - 1
    return out / 3


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def bass_note(freq, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(4 * np.pi * freq * t) + 0.15 * np.sin(6 * np.pi * freq * t)
    e = np.minimum(1, np.arange(n) / (0.005 * SR)) * env_exp(n, dur * 0.7)
    return np.tanh(sig * 1.6) * e * 0.5 * vel


def chord_stab(freqs, dur, cutoff=1800, vel=1.0):
    n = int(dur * SR)
    out = lowpass(sum(saw(f, n) for f in freqs) / len(freqs), cutoff)
    e = np.minimum(1, np.arange(n) / (0.01 * SR)) * env_exp(n, dur * 0.5)
    return out * e * 0.55 * vel


def pad(freqs, dur, cutoff=1200, vel=1.0):
    n = int(dur * SR)
    out = lowpass(sum(saw(f, n, detune=0.007) for f in freqs) / len(freqs), cutoff)
    e = np.ones(n)
    a = int(0.4 * SR)
    e[:a] = np.linspace(0, 1, a)
    r = int(min(1.2 * SR, n * 0.5))
    e[-r:] *= np.linspace(1, 0, r)
    return out * e * 0.4 * vel


def pluck(freq, dur=0.5, vel=1.0):
    t = np.arange(int(dur * SR)) / SR
    tri = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * freq * t))
    return tri * env_exp(len(t), 0.12) * 0.4 * vel


# ---- drums ----
bar_t = 0.0
while bar_t < OUTRO_START - 0.01:
    intro = bar_t < FULL_START
    brk = bar_t >= BREAK_START
    for b in range(4):
        t = bar_t + b * BEAT
        if not brk:
            add(kick(0.85 if intro else 1.0), t)
        elif b == 0:
            add(kick(0.8), t)
        if not brk:
            add(hat(open_=(b == 3 and not intro), vel=0.8 if intro else 1.0), t + BEAT / 2, pan=0.25)
        if not intro and not brk:
            add(hat(vel=0.45), t, pan=-0.2)
    if not intro:
        add(clap(0.6 if brk else 0.9), bar_t + 1 * BEAT)
        add(clap(0.6 if brk else 0.9), bar_t + 3 * BEAT)
    bar_t += BAR

# ---- bass: driving 8ths, octave jumps on 4th and 8th ----
bar_t, ci = FULL_START, 0
while bar_t < BREAK_START - 0.01:
    root = hz(BASS[ci % len(BASS)])
    for e8 in range(8):
        f = root * (2 if e8 in (3, 7) else 1)
        add(bass_note(f, BEAT / 2 * 0.9, 1.0 if e8 % 2 == 0 else 0.75), bar_t + e8 * BEAT / 2)
    bar_t += BAR
    ci += 1

# ---- chords ----
add(pad([hz(m) for m in CHORDS[0]], FULL_START, cutoff=700), 0.0, gain=0.8)
bar_t, ci = FULL_START, 0
while bar_t < BREAK_START - 0.01:
    freqs = [hz(m) for m in CHORDS[ci % len(CHORDS)]]
    for pos in (1.5, 3.5):
        add(chord_stab(freqs, BEAT * 0.9, cutoff=2000, vel=0.9), bar_t + pos * BEAT, pan=0.15)
    add(chord_stab(freqs, BEAT * 1.6, cutoff=1200, vel=0.5), bar_t, pan=-0.1)
    bar_t += BAR
    ci += 1
add(pad([hz(m) for m in CHORDS[0]], BAR * 2, cutoff=1500, vel=1.1), BREAK_START)
add(pad([hz(m) for m in CHORDS[1]], BAR * 1.4, cutoff=1300, vel=1.0), OUTRO_START)
add(pad([hz(m) for m in CHORDS[2] + [72]], DUR - (OUTRO_START + BAR * 1.4) + 0.5, cutoff=1100, vel=0.9),
    OUTRO_START + BAR * 1.4)

# ---- arp (full section) + sparse outro plucks ----
bar_t, ci = FULL_START + BAR, 1
while bar_t < BREAK_START - 0.01:
    base = CHORDS[ci % len(CHORDS)]
    seq = [base[0] + 12, base[1] + 12, base[2] + 12, base[3] + 12,
           base[2] + 12, base[1] + 12, base[0] + 24, base[2] + 12]
    for e8 in range(8):
        add(pluck(hz(seq[e8]), 0.4, 0.5), bar_t + e8 * BEAT / 2, pan=0.35 if e8 % 2 else -0.35)
    bar_t += BAR
    ci += 1
for i, (m, dt) in enumerate([(76, 0.5), (72, 1.7), (79, 2.9), (72, 4.1), (76, 5.3)]):
    add(pluck(hz(m), 0.9, 0.55), OUTRO_START + dt, pan=0.3 - 0.15 * i)

# ---- riser into full section ----
n = int(1.2 * SR)
add(lowpass(rng.standard_normal(n), 4000) * np.linspace(0, 1, n) ** 2 * 0.25, FULL_START - 1.2)

# ---- master: glue, section gains, fades, normalize ----
mix = np.tanh(np.stack([L, R]) * 1.1)
t = np.arange(N) / SR
g = np.ones(N)
g[t < FULL_START] *= 0.85
g[-int(2.5 * SR):] *= np.linspace(1, 0, int(2.5 * SR))
g[: int(0.05 * SR)] *= np.linspace(0, 1, int(0.05 * SR))
mix *= g
mix *= 10 ** (-1.5 / 20) / np.max(np.abs(mix))

ap = argparse.ArgumentParser()
ap.add_argument("-o", "--output", default="theme.wav")
out_path = ap.parse_args().output
with wave.open(out_path, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((mix.T * 32767).astype(np.int16).tobytes())
print("wrote", out_path)
