import {interpolate, useCurrentFrame} from 'remotion';
import manifest from '../data/case-manifest.json';
import {PipelineFlow} from '../components/PipelineFlow';
import {SourceBadge} from '../components/SourceBadge';
import {theme} from '../theme';

export const MemoryScene: React.FC = () => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [12, 110], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', inset: 0, background: theme.paper, color: theme.ink, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(7,17,23,.07) 1px, transparent 1px), linear-gradient(90deg, rgba(7,17,23,.07) 1px, transparent 1px)', backgroundSize: '72px 72px'}} />
      <div style={{position: 'absolute', left: 76, top: 150}}>
        <div style={{fontFamily: theme.fontMono, color: '#4D8235', fontSize: 19}}>PIPELINE 03 / FEEDBACK LOOP</div>
        <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 70, lineHeight: 1.05, marginTop: 18}}>反馈，进入记忆。</div>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 390}}>
        <PipelineFlow steps={['feedback JSON', 'validate', 'backup', 'learner profile', 'visible wiki']} startFrame={5} compact />
      </div>
      <div style={{position: 'absolute', left: 76, top: 515, width: 405, height: 500, background: theme.ink, color: theme.paper, padding: 30, border: `1px solid ${theme.lineStrong}`}}>
        <div style={{fontFamily: theme.fontMono, color: theme.signalLight, fontSize: 18}}>REVIEWABLE INPUTS</div>
        <div style={{fontFamily: theme.fontMono, fontSize: 25, lineHeight: 2.1, marginTop: 26}}>reader_feedback.json<br/>news_feedback.json</div>
        <div style={{height: 1, background: theme.lineStrong, margin: '28px 0'}} />
        <SourceBadge tone="warning">PRIVATE CONTENT HIDDEN</SourceBadge>
      </div>
      <div style={{position: 'absolute', right: 76, top: 515, width: 465, height: 500, background: 'rgba(255,255,255,.7)', padding: 30, border: '1px solid rgba(7,17,23,.23)'}}>
        <div style={{fontFamily: theme.fontMono, color: '#4D8235', fontSize: 18}}>VISIBLE WIKI / SAFE STRUCTURE</div>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 28}}>
          {manifest.privacy.allowed_structure_fields.map((field, i) => {
            const reveal = interpolate(frame, [25 + i * 12, 37 + i * 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            return <div key={field} style={{height: 120, border: '1px solid rgba(7,17,23,.22)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: theme.fontMono, fontSize: 20, background: `rgba(112,184,76,${.03 + reveal * .13})`, opacity: .35 + reveal * .65}}>{field}</div>;
          })}
        </div>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 1090}}>
        <div style={{fontFamily: theme.fontMono, fontSize: 18}}>KNOWLEDGE STATE UPDATE</div>
        <div style={{height: 18, border: '1px solid rgba(7,17,23,.22)', marginTop: 18}}><div style={{height: '100%', width: `${progress * 100}%`, background: theme.signal}} /></div>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 1210, fontFamily: theme.fontSans, fontWeight: 900, fontSize: 43, lineHeight: 1.45}}>看见过，不等于已经掌握。<br/><span style={{color: '#4D8235'}}>明确反馈，才更新知识状态。</span></div>
    </div>
  );
};
