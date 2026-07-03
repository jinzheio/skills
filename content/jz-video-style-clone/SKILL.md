---
name: jz-video-style-clone
description: Given a reference video (e.g. a competitor's product promo), analyze its visual style, pacing, and music, then produce a similar-style promo video for the current project using Remotion, including a synthesized background track matching the reference's tempo and energy arc. Use this whenever the user provides a video file or link and asks for "a video like this", "同款视频", "仿照这个风格做视频", a product promo/launch video, or wants to recreate a motion-graphics style for their own product — even if they don't mention Remotion or music.
---

# Video Style Clone

Turn a reference video into a same-style promo for the current project. The pipeline has four stages — analyze the reference, script the content, build in Remotion, add music — and each stage has a reference doc with the exact recipes. Follow the stages in order; the most common failure mode is jumping to code before the analysis is written down.

## Why this works

Motion-graphics promos (Cline, Linear, Vercel style) are highly formulaic: a hook headline, 2–4 feature beats with UI panels, a price/CTA beat, and a logo outro — all built from a small set of animation primitives (word-by-word text entrance, highlight sweep, panel slide-in, spring scale). If you extract the formula from the reference and re-instantiate it with the current project's content and brand, the result reads as "same style" even though every pixel differs. Bundled assets give you the primitives so you only write scene content.

## Stage 0 — Clarify (once, before any work)

Ask the user (one round of questions, then proceed with defaults):

1. What story/selling points should the video tell? (default: mirror the reference's narrative structure with the project's own hero copy and pricing)
2. Language of on-screen text? (default: same as reference)
3. Colors: follow the project's brand palette or copy the reference? (default: project brand — find it in the project's CSS/theme; keep the reference's *layout* and *type treatment*)
4. UI panels: recreate as coded mockups or use real screenshots? (default: coded mockups — deterministic, no secrets on screen)

Then collect project facts BEFORE writing any scenes: product name, tagline/hero copy, real feature names, real prices, logo file, brand colors, domain. Pull them from the project repo (i18n message files, `pricing`/config modules, `public/` brand assets). Never invent prices or claims — wrong numbers in a rendered video are expensive to miss.

## Stage 1 — Analyze the reference

Read `references/style-analysis.md` and follow it. In short:

- Extract 1 frame/second with ffmpeg, view them, and write a **style sheet**: background color, type scale/weight, accent color + highlight mechanic, panel chrome, pill/badge shapes, scene list with timings.
- Run `scripts/analyze_audio.py <video>` to get duration, BPM estimate, energy arc (section boundaries), and a spectrogram image to eyeball.

Write the style sheet down (a short markdown block in your reply or a scratch file). Every later decision traces back to it.

## Stage 2 — Script the video

Map the reference's scene structure onto the project's content: one line per scene with start frame, duration, on-screen text, and which primitive it uses. Keep total duration within ±15% of the reference. Put the timeline in a single `TL` constant (see the template) so scenes never overlap by accident.

## Stage 3 — Build with Remotion

Read `references/remotion-build.md`. It covers project layout, the bundled component primitives (`assets/components/`), fonts (ship woff2 in the project, load via `FontFace` + `delayRender` — never rely on system fonts or Google Fonts CDN), emoji pitfalls, and scene composition patterns. Copy the assets, recolor via one `theme.ts`, write scenes.

## Stage 4 — Music

Read `references/music.md`. Use `scripts/make_music.py` as the starting point: set BPM and section boundaries from the Stage 1 audio analysis, align the breakdown/outro to the video's price-reveal and logo scenes, render a WAV, encode to `.m4a`, reference it with `<Audio src={staticFile(...)}>` in the composition. If the user has a licensed track, skip synthesis and just align/trim it.

## Stage 5 — Render, verify, deliver

1. Render: `npx remotion render <CompositionId> out/video.mp4` (add `--concurrency=1` on small machines; chunked rendering recipe and sandbox troubleshooting are in `references/rendering.md` — read it if the render fails or you are in a restricted/sandboxed environment).
2. **Verify with your eyes**: extract 6–10 frames spread across the video (`ffmpeg -vf "select='eq(n,45)+eq(n,300)+...'"`), view them, and compare against the Stage 1 style sheet. Check: fonts actually loaded (not fallback serif), no emoji tofu boxes, panels sized to content (no big empty bottoms), text not clipped, prices/names correct.
3. Verify audio: `ffmpeg -af volumedetect` — aim for mean around −12 to −14 dB, max below −0.5 dB; confirm music sections land on the intended scenes.
4. Fix and re-render only the affected frame ranges if the renderer supports `--frames`.
5. Deliver the mp4 into the project (e.g. `video/` dir) and leave the Remotion source in the repo (e.g. `src/remotion-video/`) with `package.json` scripts (`video:promo:studio`, `video:promo:render`) so the team can iterate.

## Checklist before calling it done

- [ ] Style sheet written from actual frames (not memory) and music analysis run
- [ ] All product facts (names, prices, copy) came from the project repo
- [ ] Fonts bundled + loaded via FontFace; verified in rendered frames
- [ ] Music arc aligned to scene timeline; levels checked
- [ ] Sampled rendered frames reviewed against the style sheet
- [ ] Remotion source + render scripts committed to the project, final mp4 delivered
