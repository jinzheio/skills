# Stage 4: Background music

Two paths: user-provided licensed track (just trim/align/fade with ffmpeg), or synthesize one matching the reference's tempo and arc. This doc covers synthesis.

## Why synthesis works here

Promo beds are structurally simple: a steady electronic groove with an energy arc (sparse intro → full mix → breakdown → outro). Listeners judge *fit* (tempo, arc aligned to picture) more than sound design. A clean synthesized track that hits the video's beats reads better than a great track that ignores them.

## Workflow

1. From Stage 1's `analyze_audio.py` output take: **BPM**, **section boundaries** (where the mix opens up / breaks down / ends), and total duration.
2. Copy `scripts/make_music.py` to a scratch dir and edit the parameter block at the top:
   - `BPM`, `DUR`
   - `FULL_START`, `BREAK_START`, `OUTRO_START` — express these in bars and **align them to the video timeline**, not the reference's: the breakdown should land on the price-reveal/credibility scene, the outro pad on the logo scene, the fade should complete at video end.
   - chords: default `Fmaj7 – Am7 – C – G6` is a safe warm-neutral loop; shift the whole table up/down a few semitones to taste
3. Run it → writes a stereo WAV.
4. Post-process and encode (tame the synth's top end, leave ~1 dB headroom):

```bash
ffmpeg -y -i theme.wav -af "treble=g=-2.5:f=9000,volume=-2.5dB" \
  -c:a aac -b:a 192k <project>/public/music/promo-theme.m4a
```

5. Reference it in the composition: `<Audio src={staticFile('music/promo-theme.m4a')} />` — now every future render includes it.
6. If the final mp4 was already rendered without audio, mux instead of re-rendering:

```bash
ffmpeg -y -i video.mp4 -i promo-theme.m4a -map 0:v -map 1:a -c copy -shortest out.mp4
```

## Verify

- `ffmpeg -i out.mp4 -af volumedetect -f null -` → mean around −12…−14 dB (compare to the reference's measured mean), max ≤ −0.4 dB (0.0 means clipping — lower the volume and re-encode)
- Spectrogram the synthesized track (`showspectrumpic`) and compare the arc shape against the reference's spectrogram
- Check the seams: scrub the frames where sections change and confirm they coincide with scene changes

## What the synth script contains

`make_music.py` is stdlib+numpy only (no DAW, no samples): kick (pitch-dropped sine + click), hats (double-differentiated noise = crude high-pass), clap (multi-tap noise burst), bass (saturated sine+harmonics playing driving 8ths), chord stabs and pads (detuned saws through a one-pole low-pass), plucks (triangle arps), a noise riser into the full section, tanh bus glue, section gain automation, fade-out. Every sound is a small function — swap patterns or drop instruments freely; e.g. delete the arp block for a calmer bed, halve kick density for half-time feel.
