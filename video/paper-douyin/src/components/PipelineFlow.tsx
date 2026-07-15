import {interpolate, useCurrentFrame} from 'remotion';
import {theme} from '../theme';

export const PipelineFlow: React.FC<{
  steps: string[];
  startFrame?: number;
  compact?: boolean;
}> = ({steps, startFrame = 0, compact = false}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{display: 'flex', alignItems: 'center', width: '100%', gap: compact ? 8 : 12}}>
      {steps.map((step, i) => {
        const active = interpolate(frame, [startFrame + i * 7, startFrame + i * 7 + 7], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <div key={step} style={{display: 'contents'}}>
            <div
              style={{
                flex: '0 1 auto',
                border: `1px solid rgba(112,184,76,${0.25 + active * 0.75})`,
                background: `rgba(112,184,76,${0.04 + active * 0.13})`,
                color: active > 0.6 ? theme.signalLight : theme.paperMuted,
                padding: compact ? '9px 9px' : '12px 14px',
                fontFamily: theme.fontMono,
                fontSize: compact ? 15 : 18,
                fontWeight: 700,
                whiteSpace: 'nowrap',
                transform: `translateY(${(1 - active) * 6}px)`,
                opacity: 0.45 + active * 0.55,
              }}
            >
              {step}
            </div>
            {i < steps.length - 1 ? (
              <div style={{height: 1, flex: 1, minWidth: 6, background: `rgba(112,184,76,${0.18 + active * 0.62})`}} />
            ) : null}
          </div>
        );
      })}
    </div>
  );
};
