import {Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import manifest from '../data/case-manifest.json';
import {SourceBadge} from '../components/SourceBadge';
import {theme} from '../theme';

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const inValue = interpolate(frame, [0, 20], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', inset: 0, background: theme.ink, color: theme.paper, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(240,237,229,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(240,237,229,.05) 1px, transparent 1px)', backgroundSize: '72px 72px'}} />
      <div style={{position: 'absolute', left: 76, top: 165, fontFamily: theme.fontMono, color: theme.signalLight, fontSize: 19}}>PaperTraceTRACE / LOCAL RESEARCH SYSTEM</div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 330, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, opacity: inValue}}>
        <div style={{height: 420, overflow: 'hidden', border: `1px solid ${theme.lineStrong}`, background: theme.paper}}><Img src={staticFile('cases/paper/source-page-1.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} /></div>
        <div style={{height: 420, overflow: 'hidden', border: `1px solid ${theme.lineStrong}`, background: theme.paper}}><Img src={staticFile('cases/news/briefing-reader.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} /></div>
        <div style={{height: 420, border: `1px solid ${theme.lineStrong}`, padding: 20, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
          <SourceBadge>FEEDBACK</SourceBadge>
          <div style={{fontFamily: theme.fontMono, fontSize: 20, lineHeight: 2, marginTop: 24}}>concepts<br/>events<br/>sources<br/>review_queue</div>
        </div>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 850, opacity: inValue}}>
        <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 108, lineHeight: .98, letterSpacing: -4}}>三条入口，<br/><span style={{color: theme.signalLight}}>一套记忆。</span></div>
        <div style={{fontFamily: theme.fontSans, fontSize: 38, lineHeight: 1.5, marginTop: 50}}>让每一次阅读，<br/>成为下一次研究的起点。</div>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, bottom: 160, borderTop: `1px solid ${theme.lineStrong}`, paddingTop: 28, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end'}}>
        <div><div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 54}}>PaperTraceTRACE</div><div style={{fontFamily: theme.fontMono, fontSize: 17, marginTop: 8}}>LOCAL RESEARCH · COMPOUNDING KNOWLEDGE</div></div>
        <div style={{fontFamily: theme.fontMono, fontSize: 15, textAlign: 'right', opacity: .68}}>READER: {manifest.paper.validation_status.toUpperCase()}<br/>BRIEFING: COMPLETE</div>
      </div>
    </div>
  );
};
