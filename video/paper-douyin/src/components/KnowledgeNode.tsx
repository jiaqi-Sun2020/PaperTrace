import {interpolate, useCurrentFrame} from 'remotion';
import {theme} from '../theme';

export const KnowledgeNode: React.FC<{
  label: string;
  x: number;
  y: number;
  delay: number;
  size?: number;
}> = ({label, x, y, delay, size = 112}) => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [delay, delay + 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        position: 'absolute', left: x, top: y, width: size, height: size,
        borderRadius: '50%', border: `2px solid ${theme.signal}`,
        background: 'rgba(112,184,76,.12)', color: theme.paper,
        display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', whiteSpace: 'pre-line',
        fontFamily: theme.fontMono, fontSize: 17, fontWeight: 700,
        transform: `scale(${0.65 + reveal * 0.35})`, opacity: reveal,
        boxShadow: `0 0 ${30 * reveal}px rgba(112,184,76,.24)`,
      }}
    >
      {label}
    </div>
  );
};
