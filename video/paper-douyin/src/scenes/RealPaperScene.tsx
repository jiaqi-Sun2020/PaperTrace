import {Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import manifest from '../data/case-manifest.json';
import {PipelineFlow} from '../components/PipelineFlow';
import {SourceBadge} from '../components/SourceBadge';
import {theme} from '../theme';

export const RealPaperScene: React.FC = () => {
  const frame = useCurrentFrame();
  const titleIn = interpolate(frame, [0, 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const visualIn = interpolate(frame, [25, 48], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const switchToFigure = interpolate(frame, [92, 110], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', inset: 0, background: theme.ink, color: theme.paper, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(240,237,229,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(240,237,229,.045) 1px, transparent 1px)', backgroundSize: '72px 72px'}} />
      <div style={{position: 'absolute', left: 76, right: 76, top: 150, opacity: titleIn}}>
        <div style={{fontFamily: theme.fontMono, color: theme.signalLight, fontSize: 19, letterSpacing: 1.5}}>PIPELINE 01 / READER</div>
        <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 45, lineHeight: 1.08, marginTop: 18}}>{manifest.paper.title}</div>
        <div style={{fontFamily: theme.fontMono, fontSize: 18, opacity: .72, marginTop: 16}}>{manifest.paper.authors.join(' · ')} · {manifest.paper.doi_or_arxiv}</div>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 415}}>
        <PipelineFlow steps={['SOURCE PDF', 'reader bundle', 'reader_wiki', 'PASS', 'Reader']} startFrame={8} compact />
      </div>
      <div style={{position: 'absolute', left: 76, top: 520, width: 420, height: 650, border: `1px solid ${theme.lineStrong}`, overflow: 'hidden', opacity: 1 - switchToFigure * .45, transform: `translateX(${(1 - visualIn) * -35}px)`}}>
        <Img src={staticFile('cases/paper/source-page-2.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} />
        <div style={{position: 'absolute', left: 18, bottom: 18}}><SourceBadge tone="paper">SOURCE PDF · PAGE 2</SourceBadge></div>
      </div>
      <div style={{position: 'absolute', right: 76, top: 520, width: 490, height: 650, border: `1px solid ${theme.lineStrong}`, background: theme.paper, color: theme.ink, overflow: 'hidden', transform: `translateX(${(1 - visualIn) * 45}px)`}}>
        <div style={{padding: '26px 28px 20px', borderBottom: '1px solid rgba(7,17,23,.18)'}}>
          <div style={{fontFamily: theme.fontMono, fontSize: 18, color: '#4D8235'}}>REAL OBJECT / EQ. (10)</div>
          <div style={{fontFamily: 'Georgia, serif', fontSize: 37, marginTop: 22, whiteSpace: 'nowrap'}}>|χ(t+ε)⟩ = e<sup>−iĤε</sup>|ψ(t)⟩</div>
        </div>
        <div style={{position: 'relative', height: 350, overflow: 'hidden'}}>
          <Img src={staticFile('cases/paper/fig3-circuit-depth.png')} style={{width: '100%', height: '100%', objectFit: 'contain', transform: `scale(${1 + switchToFigure * .05})`}} />
        </div>
        <div style={{padding: '16px 28px', fontFamily: theme.fontSans, fontSize: 22, lineHeight: 1.45}}>CETE 将每个时间步重写为一次相关化问题；图 3 比较 CETE 与序列演化的线路深度。</div>
        <div style={{position: 'absolute', right: 18, bottom: 18}}><SourceBadge>SOURCE PAGE 2 · FIG.3 PAGE 3</SourceBadge></div>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 1210, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{fontFamily: theme.fontMono, fontSize: 20}}>reader_interactive.html</div>
        <SourceBadge>STRUCTURE VALIDATION: PASS</SourceBadge>
      </div>
      <div style={{position: 'absolute', left: 76, top: 1280, right: 76, borderTop: `1px solid ${theme.lineStrong}`, paddingTop: 24, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, fontFamily: theme.fontMono, fontSize: 18}}>
        <div>FORMULAS<br/><b style={{fontSize: 32, color: theme.signalLight}}>15</b></div>
        <div>CONCEPTS<br/><b style={{fontSize: 32, color: theme.signalLight}}>33</b></div>
        <div>WARNINGS<br/><b style={{fontSize: 32, color: theme.warning}}>{manifest.paper.validation_warnings}</b></div>
      </div>
      <div style={{position: 'absolute', left: 76, bottom: 190, fontFamily: theme.fontMono, fontSize: 17, color: theme.warning}}>PREPRINT · NOT PEER REVIEWED</div>
    </div>
  );
};
