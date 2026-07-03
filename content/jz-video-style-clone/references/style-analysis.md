# Stage 1: Analyzing the reference video

The goal is a written **style sheet** — a compact spec you (and the user) can check the final video against. Don't skip writing it down; "I looked at the video" is not a spec.

## 1. Probe the container

```bash
ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=width,height,r_frame_rate,codec_type "<ref.mp4>"
```

Note resolution, aspect ratio (4:3 vs 16:9 changes layout decisions), fps, duration.

## 2. Extract and view frames

```bash
mkdir -p frames
ffmpeg -v error -i "<ref.mp4>" -vf fps=1 -q:v 3 frames/f%02d.jpg
```

View them (image-capable models: read ~10 frames spread across the video; more near scene changes). If you cannot view images, extract more frames and ask the user to describe key ones, or run OCR — but visual inspection is strongly preferred.

## 3. Write the style sheet

Fill in every row — unknowns become guesses that drift:

| Element | What to record |
|---|---|
| Background | exact-ish color (cream `#FAFAF3`? white? dark?) |
| Headline type | weight (700/800?), approx size relative to frame height, letter-spacing (tight?), color |
| Secondary type | color (gray?), weight, size ratio vs headline |
| Accent mechanic | highlight sweep behind words? underline? color block? record its color + border radius + slight rotation if any |
| Decorative elements | floating pills/badges? shapes? their fill, border, shadow, what text they carry |
| UI panels | dark or light chrome, corner radius, mac traffic-light dots?, title bar text style, monospace content?, accent colors inside |
| Motion | how text enters (word-by-word pop? fade-rise?), how panels enter (slide from right?), transition between scenes (hard cut? fade?) |
| Scene list | one line per scene: `[start s]–[end s]: description` |

## 4. Deduce the scene formula

Typical promo formula (verify against your scene list, don't assume):

1. **Hook** — big claim, accent highlight, decorative pills drifting
2. **Problem** — gray subhead ("tired of X?")
3. **Feature beats ×2–4** — short bold claim left, UI panel right
4. **Credibility/`powered by` beat** — centered statement with highlight
5. **Price reveal** — huge number, small caveats
6. **Outro** — logo, name, tagline, URL pill

Map each reference scene to one of these roles; you'll re-instantiate the same roles with project content in Stage 2.

## 5. Analyze the audio

```bash
python3 scripts/analyze_audio.py "<ref.mp4>" --out-dir ./audio-analysis
```

It prints duration, BPM candidates (autocorrelation of the onset envelope), and section boundaries from the energy envelope, and writes `spectrogram.png`. View the spectrogram and describe the arc in words, e.g.:

> quiet rhythmic intro 0–10s → full bright mix 10–28s → breakdown 28s → soft fading outro

Record: BPM, where the music "opens up", where it breaks down, whether the ending fades or hits a button. You will feed these numbers to `make_music.py` in Stage 4.

If the video has a voiceover instead of/besides music, note it — this skill only reproduces the music bed; voiceover is out of scope unless the user asks.
