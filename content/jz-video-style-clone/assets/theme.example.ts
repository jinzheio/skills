// Copy to src/remotion-video/theme.ts in the project and fill in from
// (a) your Stage 1 style sheet and (b) the project's brand palette.

export const COLORS = {
  bg: '#FAFAF3', // reference background (cream/white/dark)
  ink: '#141210', // headline text
  gray: '#8A857D', // dim secondary
  grayDark: '#5C5850', // secondary text
  accent: '#E65719', // PROJECT brand accent (from its CSS/theme)
  accentSoft: '#FFC9A8', // highlight-sweep fill: accent hue, high lightness
  accentSofter: '#FFE3D1', // URL pill background in outro
  panelBg: '#191614', // dark UI panel
  panelBorder: '#2E2A26',
  panelText: '#D8D2C8',
  panelDim: '#8A8378',
  panelAccent: '#FF7A3D', // accent, brightened for dark backgrounds
  panelGreen: '#7BD88F', // success
} as const;

export const FONT = {
  sans: "'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif",
  mono: "'JetBrains Mono', 'SF Mono', 'Fira Code', Menlo, Consolas, monospace",
} as const;

export const VIDEO = {
  width: 1440, // match the reference's aspect (1440x1080 = 4:3)
  height: 1080,
  fps: 30,
} as const;

// The single source of truth for scene timing (frames). Derive everything
// from this — never scatter frame numbers through scene files.
export const TL = {
  hook: { from: 0, duration: 170 },
  feature1: { from: 170, duration: 185 },
  feature2: { from: 355, duration: 185 },
  feature3: { from: 540, duration: 185 },
  poweredBy: { from: 725, duration: 120 },
  pricing: { from: 845, duration: 165 },
  outro: { from: 1010, duration: 150 },
} as const;

export const TOTAL_FRAMES = TL.outro.from + TL.outro.duration;
