import { continueRender, delayRender, staticFile } from 'remotion';

/**
 * Loads the promo's fonts from /public/fonts so renders are deterministic
 * (no network dependency, same result locally and in CI).
 */
const FACES: Array<{ family: string; file: string; weight: string }> = [
  { family: 'Inter', file: 'fonts/Inter-Medium-subset.woff2', weight: '500' },
  { family: 'Inter', file: 'fonts/Inter-SemiBold-subset.woff2', weight: '600' },
  { family: 'Inter', file: 'fonts/Inter-Bold-subset.woff2', weight: '700' },
  { family: 'Inter', file: 'fonts/Inter-ExtraBold-subset.woff2', weight: '800' },
  { family: 'JetBrains Mono', file: 'fonts/jetbrains-mono-latin-400-normal.woff2', weight: '400' },
];

let loaded = false;

export const loadFonts = () => {
  if (loaded || typeof document === 'undefined') return;
  loaded = true;
  const handle = delayRender('Loading fonts');
  Promise.all(
    FACES.map(async ({ family, file, weight }) => {
      const font = new FontFace(family, `url(${staticFile(file)}) format('woff2')`, { weight });
      await font.load();
      document.fonts.add(font);
    }),
  )
    .then(() => continueRender(handle))
    .catch((err) => {
      // Fall back to system fonts rather than failing the render.
      // eslint-disable-next-line no-console
      console.error('Font loading failed', err);
      continueRender(handle);
    });
};
