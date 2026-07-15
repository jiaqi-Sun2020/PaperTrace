import type {Caption} from '@remotion/captions';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import captionsJson from '../data/captions.json';
import {theme} from '../theme';

const captions = captionsJson as Caption[];

export const SafeSubtitle: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const ms = frame / fps * 1000;
  const active = captions.find((caption) => ms >= caption.startMs && ms < caption.endMs);
  if (!active) return null;
  return (
    <div
      style={{
        position: 'absolute', left: 82, right: 82, bottom: 292,
        display: 'flex', justifyContent: 'center', pointerEvents: 'none', zIndex: 100,
      }}
    >
      <div
        style={{
          maxWidth: 900, background: 'rgba(7,17,23,.84)', color: theme.paper,
          border: '1px solid rgba(240,237,229,.25)', padding: '14px 25px 16px',
          fontFamily: theme.fontSans, fontWeight: 800, fontSize: 43, lineHeight: 1.25,
          textAlign: 'center', boxShadow: '0 12px 36px rgba(0,0,0,.22)',
        }}
      >
        {active.text}
      </div>
    </div>
  );
};
