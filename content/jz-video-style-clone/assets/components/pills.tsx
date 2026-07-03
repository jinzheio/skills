import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';
import { COLORS, FONT } from '../theme';

type PillSpec = {
  name: string;
  tag?: string;
  x: number; // % of width
  y: number; // % of height
  rotate: number;
  drift: number; // px drifted over the scene
  delay: number; // frames
};

// EDIT ME: name the current project's ecosystem — integrations, features,
// model names, whatever the hook scene should evoke. Keep 6–9 pills,
// scattered near the edges (some partially off-frame looks intentional).
const PILLS: PillSpec[] = [
  { name: 'FeatureOne', tag: 'core', x: 4, y: 8, rotate: -8, drift: 30, delay: 0 },
  { name: 'Integration', tag: 'api', x: 78, y: 6, rotate: 6, drift: -26, delay: 3 },
  { name: 'Platform', x: 88, y: 34, rotate: 9, drift: 22, delay: 6 },
  { name: 'Tooling', x: -2, y: 38, rotate: 5, drift: -20, delay: 9 },
  { name: 'Automation', tag: 'jobs', x: 6, y: 78, rotate: -6, drift: 26, delay: 12 },
  { name: 'Scheduler', x: 82, y: 82, rotate: -9, drift: -30, delay: 15 },
  { name: 'Memory', x: 40, y: 92, rotate: 4, drift: 18, delay: 18 },
  { name: 'Search', tag: 'web', x: 30, y: -2, rotate: -5, drift: -18, delay: 21 },
];

/** Scattered capability pills drifting at the edges of the hook scene. */
export const FloatingPills: React.FC<{ exitStart?: number }> = ({ exitStart = 9999 }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
      {PILLS.map((p) => {
        const enter = interpolate(frame - p.delay, [0, 14], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        const exit = interpolate(frame, [exitStart, exitStart + 16], [1, 0], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        const drift = interpolate(frame, [0, 170], [0, p.drift]);
        return (
          <div
            key={p.name}
            style={{
              position: 'absolute',
              left: `${p.x}%`,
              top: `${p.y}%`,
              opacity: enter * exit,
              transform: `translateY(${drift + (1 - enter) * 20}px) rotate(${p.rotate}deg) scale(${0.9 + enter * 0.1})`,
              background: '#FFFFFF',
              border: '1px solid #E8E3D9',
              boxShadow: '0 4px 14px rgba(20,18,16,0.07)',
              borderRadius: 999,
              padding: '14px 26px',
              display: 'flex',
              alignItems: 'baseline',
              gap: 12,
            }}
          >
            <span
              style={{
                fontFamily: FONT.sans,
                fontWeight: 700,
                fontSize: 30,
                color: COLORS.ink,
                letterSpacing: '-0.01em',
              }}
            >
              {p.name}
            </span>
            {p.tag && (
              <span style={{ fontFamily: FONT.mono, fontSize: 20, color: COLORS.gray }}>{p.tag}</span>
            )}
          </div>
        );
      })}
    </div>
  );
};
