import type {CSSProperties} from 'react';
import {theme} from '../theme';

export const SourceBadge: React.FC<{
  children: React.ReactNode;
  tone?: 'signal' | 'paper' | 'warning';
  style?: CSSProperties;
}> = ({children, tone = 'signal', style}) => {
  const colors = {
    signal: [theme.signalLight, 'rgba(112,184,76,0.14)'],
    paper: [theme.paper, 'rgba(240,237,229,0.08)'],
    warning: [theme.warning, 'rgba(241,196,83,0.12)'],
  } as const;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        border: `1px solid ${colors[tone][0]}`,
        background: colors[tone][1],
        color: colors[tone][0],
        padding: '7px 12px',
        borderRadius: 4,
        fontFamily: theme.fontMono,
        fontSize: 19,
        fontWeight: 700,
        letterSpacing: 0.8,
        lineHeight: 1,
        ...style,
      }}
    >
      {children}
    </span>
  );
};
