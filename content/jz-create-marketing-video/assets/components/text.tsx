import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { COLORS } from '../theme';

/**
 * Words pop in one by one (slight rise + fade), like kinetic-typography promos.
 * `delay` is the frame (relative to the enclosing Sequence) the first word starts.
 */
export const WordsIn: React.FC<{
  text: string;
  delay?: number;
  stagger?: number;
  style?: React.CSSProperties;
}> = ({ text, delay = 0, stagger = 3, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(' ');
  return (
    <span style={style}>
      {words.map((word, i) => {
        const start = delay + i * stagger;
        const s = spring({
          frame: frame - start,
          fps,
          config: { damping: 16, mass: 0.6, stiffness: 140 },
        });
        const opacity = interpolate(frame - start, [0, 6], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <span
            key={i}
            style={{
              display: 'inline-block',
              whiteSpace: 'pre',
              opacity,
              transform: `translateY(${(1 - s) * 28}px)`,
            }}
          >
            {word}
            {i < words.length - 1 ? ' ' : ''}
          </span>
        );
      })}
    </span>
  );
};

/**
 * Accent highlight that sweeps in behind a run of text (rounded marker style).
 */
export const Highlight: React.FC<{
  children: React.ReactNode;
  delay?: number;
  color?: string;
  padding?: string;
}> = ({ children, delay = 0, color = COLORS.accentSoft, padding = '0.02em 0.18em' }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 24, mass: 0.8, stiffness: 90 },
  });
  const width = Math.max(0, Math.min(1, s)) * 100;
  return (
    <span style={{ position: 'relative', display: 'inline-block', padding }}>
      <span
        style={{
          position: 'absolute',
          inset: 0,
          background: color,
          borderRadius: '0.28em',
          transformOrigin: 'left center',
          width: `${width}%`,
          transform: 'rotate(-0.6deg)',
        }}
      />
      <span style={{ position: 'relative' }}>{children}</span>
    </span>
  );
};

/** Simple fade + rise entrance for a block. */
export const RiseIn: React.FC<{
  children: React.ReactNode;
  delay?: number;
  distance?: number;
  style?: React.CSSProperties;
}> = ({ children, delay = 0, distance = 30, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 20, mass: 0.7, stiffness: 110 },
  });
  const opacity = interpolate(frame - delay, [0, 10], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div style={{ opacity, transform: `translateY(${(1 - s) * distance}px)`, ...style }}>
      {children}
    </div>
  );
};

/** Fade the whole scene out over its final `fadeFrames`. */
export const SceneFade: React.FC<{
  durationInFrames: number;
  fadeFrames?: number;
  children: React.ReactNode;
}> = ({ durationInFrames, fadeFrames = 10, children }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [durationInFrames - fadeFrames, durationInFrames - 2],
    [1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  return <div style={{ opacity, width: '100%', height: '100%' }}>{children}</div>;
};
