import {interpolate, useCurrentFrame} from 'remotion';
import {SourceBadge} from '../components/SourceBadge';
import {theme} from '../theme';

export const ProductRevealScene: React.FC = () => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [0, 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const line = interpolate(frame, [12, 50], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', inset: 0, background: theme.paper, color: theme.ink, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(7,17,23,.08) 1px, transparent 1px), linear-gradient(90deg, rgba(7,17,23,.08) 1px, transparent 1px)', backgroundSize: '90px 90px'}} />
      <div style={{position: 'absolute', left: 76, top: 160, fontFamily: theme.fontMono, fontSize: 19, letterSpacing: 2}}>PaperTraceTRACE / PRODUCT SYSTEM</div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 470, transform: `translateY(${(1 - reveal) * 46}px)`, opacity: reveal}}>
        <div style={{fontFamily: theme.fontCondensed, fontSize: 106, lineHeight: .98, fontWeight: 950, letterSpacing: -4}}>一张会记忆的<br/><span style={{color: '#4D8235'}}>研究桌。</span></div>
        <div style={{width: `${line * 100}%`, height: 3, background: theme.signal, marginTop: 52}} />
        <div style={{fontFamily: theme.fontSans, fontSize: 39, lineHeight: 1.55, marginTop: 42, maxWidth: 820}}>从来源到理解，<br/>再从反馈回到下一次研究。</div>
        <div style={{display: 'flex', gap: 16, marginTop: 48, flexWrap: 'wrap'}}>
          <SourceBadge>LOCAL-FIRST</SourceBadge><SourceBadge>SOURCE-GROUNDED</SourceBadge><SourceBadge>FEEDBACK LOOP</SourceBadge>
        </div>
      </div>
      <div style={{position: 'absolute', left: 76, bottom: 170, fontFamily: theme.fontMono, fontSize: 20}}>THREE PIPELINES · ONE MEMORY</div>
    </div>
  );
};
