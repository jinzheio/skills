import React from 'react';
import { interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { COLORS, FONT } from '../theme';

/**
 * Dark UI window that slides in from the right, like the terminal panels
 * in the reference video. Children render inside the window body.
 */
export const SlideInWindow: React.FC<{
  title: string;
  delay?: number;
  width?: number;
  height?: number;
  children: React.ReactNode;
  light?: boolean;
}> = ({ title, delay = 0, width = 760, height = 860, children, light = false }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 22, mass: 0.9, stiffness: 80 },
  });
  const x = (1 - s) * 520;
  const opacity = interpolate(frame - delay, [0, 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        width,
        height,
        transform: `translateX(${x}px)`,
        opacity,
        background: light ? '#FFFFFF' : COLORS.panelBg,
        border: `1px solid ${light ? '#E8E3D9' : COLORS.panelBorder}`,
        borderRadius: 18,
        boxShadow: '0 24px 70px rgba(20,18,16,0.18)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '16px 20px',
          borderBottom: `1px solid ${light ? '#EEE9DF' : COLORS.panelBorder}`,
          flexShrink: 0,
        }}
      >
        <Dot color="#FF5F57" />
        <Dot color="#FEBC2E" />
        <Dot color="#28C840" />
        <span
          style={{
            marginLeft: 10,
            fontFamily: FONT.mono,
            fontSize: 20,
            color: light ? COLORS.gray : COLORS.panelDim,
          }}
        >
          {title}
        </span>
      </div>
      <div style={{ flex: 1, minHeight: 0 }}>{children}</div>
    </div>
  );
};

const Dot: React.FC<{ color: string }> = ({ color }) => (
  <span style={{ width: 14, height: 14, borderRadius: 999, background: color, display: 'block' }} />
);
