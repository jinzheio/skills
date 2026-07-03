# Stage 3: Building the video in Remotion

## Why Remotion

These promos are kinetic typography + UI mockups — exactly what React + springs express well. Remotion renders React to video deterministically, lives inside the product repo (same review flow as code), and re-renders are cheap after copy tweaks.

## Project layout

If the project already has Remotion (`remotion.config.ts`, `@remotion/cli` in deps), extend it. Otherwise add dev-deps `remotion`, `@remotion/cli` (matching major versions) and create:

```
src/remotion-video/
├── Root.tsx            # registerRoot + <Composition>
├── Promo.tsx           # assembles scenes with <Sequence>
├── scenes.tsx          # one component per scene
├── theme.ts            # COLORS / FONT / VIDEO / TL timeline constants
├── fonts.ts            # FontFace loader (see below)
└── components/         # copied from this skill's assets/components/
```

```ts
// remotion.config.ts (project root)
import { Config } from '@remotion/cli/config';
Config.setEntryPoint('src/remotion-video/Root.tsx');
```

Add `package.json` scripts: `"video:promo:studio": "remotion studio"`, `"video:promo:render": "remotion render <CompositionId> video/promo.mp4"`.

## The timeline lives in one place

Put every scene's `{ from, duration }` in a `TL` constant in `theme.ts` and derive `TOTAL_FRAMES` from it. Scenes receive `durationInFrames` as a prop so they can fade themselves out. This is what keeps a 7-scene video editable — never scatter frame numbers through scene files.

```ts
export const TL = {
  hook:    { from: 0,   duration: 170 },
  setup:   { from: 170, duration: 185 },
  // ...
} as const;
```

## Bundled primitives (assets/components/)

Copy these into the project and recolor via `theme.ts` — they are the whole animation vocabulary of this style:

- `text.tsx` — `WordsIn` (word-by-word spring pop), `Highlight` (accent sweep growing left→right behind text, slight −0.6° rotation), `RiseIn` (fade+rise block), `SceneFade` (scene fades itself out over its last ~10 frames)
- `window.tsx` — `SlideInWindow`: dark (or light) UI window with mac dots + mono title, springs in from the right. Put mock UI inside as children
- `pills.tsx` — `FloatingPills`: scattered rounded badges drifting at the frame edges for the hook scene; edit the pill list to name the project's ecosystem (integrations, features)

Also in `assets/`: `theme.example.ts` (copy as `theme.ts`, fill from your style sheet + brand palette) and `fonts.example.ts` (copy as `fonts.ts`, adjust the font file list).

Spring feel used throughout (matches the genre): entrances `{ damping: 14–22, mass: 0.6–0.9, stiffness: 80–160 }`; pair every spring with a short 6–12 frame opacity ramp so nothing pops in at full alpha.

## Mock UI panels

Recreate app UIs as small React components, don't screenshot:

- **Deploy/progress panel**: mono font, step list where each step flips `· → ○ → ✓` on a frame schedule, finish with a green "live" pill
- **Chat panel** (Telegram/Slack/iMessage style): header with avatar + "online", bubbles that spring in on a schedule, user bubbles right-aligned
- **Checklist/dashboard panel**: `▸ Feature  dim explanation` rows appearing one by one

Schedule content by absolute frame within the scene (`at: 15, at: 40, ...`) — data-driven arrays of `{text, at}` keep scenes readable. Size the panel height to its content; a half-empty panel is the most common "AI-made" tell. Fill realistic content (plausible file names, timings like "2m 41s") but keep it fictional — no real emails/tokens.

## Fonts — do this exactly

System fonts differ across render machines and Google Fonts CDN may be unreachable; both cause silent style drift. So:

1. Ship woff2 files in the project's `public/fonts/` (Inter or similar grotesk for UI text; JetBrains Mono or similar for panel/mono text; npm packages `inter-ui` and `@fontsource/*` contain woff2 you can copy — latin subsets suffice for English text)
2. Load with `FontFace` + `delayRender` so no frame renders before fonts are ready:

```ts
import { continueRender, delayRender, staticFile } from 'remotion';
const handle = delayRender('fonts');
Promise.all(FACES.map(async ({ family, file, weight }) => {
  const f = new FontFace(family, `url(${staticFile(file)}) format('woff2')`, { weight });
  await f.load(); document.fonts.add(f);
})).then(() => continueRender(handle)).catch(() => continueRender(handle));
```

3. Call it once at module scope in `Root.tsx`.
4. In verification frames, confirm the real font rendered (fallback fonts are wider/rounder — compare a headline against the reference).

## Emoji and special glyphs

Headless render environments usually lack color-emoji fonts → tofu boxes. Avoid emoji in on-screen text. Use safe glyphs that exist in DejaVu/common fallbacks: `✓ ○ · ▸ ●`, or inline SVG (e.g. the project logo as a React SVG component — copy the path data from the project's `public/` SVG so there's no runtime asset dependency).

## Brand colors

Pull the accent from the project theme (CSS custom properties, Tailwind config). If it's in `oklch()`, convert to hex for use in the video. Derive a soft variant for highlight sweeps (roughly: same hue, high lightness — e.g. accent `#E65719` → sweep `#FFC9A8`) rather than using the accent at full strength behind black text.

## Composition

```tsx
export const Promo: React.FC = () => (
  <AbsoluteFill style={{ background: COLORS.bg }}>
    <Audio src={staticFile('music/promo-theme.m4a')} />
    <Sequence from={TL.hook.from} durationInFrames={TL.hook.duration}>
      <HookScene durationInFrames={TL.hook.duration} />
    </Sequence>
    {/* ... one <Sequence> per scene, hard cuts + self-fades match the genre */}
  </AbsoluteFill>
);
```

Match the reference's resolution/aspect (e.g. 1440×1080 for 4:3) and 30 fps unless the reference differs.
