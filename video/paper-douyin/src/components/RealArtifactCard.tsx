import type {CSSProperties} from 'react';
import {theme} from '../theme';
import {SourceBadge} from './SourceBadge';

export const RealArtifactCard: React.FC<{
  index: string;
  title: string;
  meta: string;
  badge?: string;
  children?: React.ReactNode;
  style?: CSSProperties;
  light?: boolean;
}> = ({index, title, meta, badge, children, style, light = false}) => (
  <div
    style={{
      position: 'relative',
      border: `1px solid ${light ? 'rgba(7,17,23,.22)' : theme.lineStrong}`,
      background: light ? 'rgba(240,237,229,.95)' : 'rgba(7,17,23,.92)',
      color: light ? theme.ink : theme.paper,
      padding: '24px 26px 22px',
      boxShadow: '0 18px 50px rgba(0,0,0,.18)',
      overflow: 'hidden',
      ...style,
    }}
  >
    <div style={{display: 'flex', justifyContent: 'space-between', gap: 16}}>
      <span style={{fontFamily: theme.fontMono, color: theme.signal, fontSize: 22}}>{index}</span>
      {badge ? <SourceBadge>{badge}</SourceBadge> : null}
    </div>
    <div style={{fontFamily: theme.fontCondensed, fontSize: 34, fontWeight: 900, lineHeight: 1.15, marginTop: 18}}>
      {title}
    </div>
    <div style={{fontFamily: theme.fontMono, fontSize: 19, opacity: 0.72, marginTop: 12}}>{meta}</div>
    {children ? <div style={{marginTop: 20}}>{children}</div> : null}
  </div>
);
