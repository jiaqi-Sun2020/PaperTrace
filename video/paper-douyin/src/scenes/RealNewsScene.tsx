import {Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import manifest from '../data/case-manifest.json';
import {PipelineFlow} from '../components/PipelineFlow';
import {SourceBadge} from '../components/SourceBadge';
import {theme} from '../theme';

export const RealNewsScene: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <div style={{position: 'absolute', inset: 0, background: theme.paper, color: theme.ink, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(7,17,23,.065) 1px, transparent 1px), linear-gradient(90deg, rgba(7,17,23,.065) 1px, transparent 1px)', backgroundSize: '72px 72px'}} />
      <div style={{position: 'absolute', left: 76, right: 76, top: 150}}>
        <div style={{fontFamily: theme.fontMono, color: '#4D8235', fontSize: 19}}>PIPELINE 02 / VERIFIED NEWS</div>
        <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 62, marginTop: 14}}>真实 AI / 量子新闻</div>
        <div style={{fontFamily: theme.fontMono, fontSize: 20, marginTop: 12}}>BRIEFING · {manifest.news_briefing.date_range}</div>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 345}}>
        <PipelineFlow steps={['Candidate', 'Official source', 'Evidence', 'Verify', 'Publish']} startFrame={0} compact />
      </div>
      <div style={{position: 'absolute', left: 76, top: 440, width: 330, height: 740, overflow: 'hidden', border: '1px solid rgba(7,17,23,.25)', boxShadow: '0 18px 44px rgba(7,17,23,.15)'}}>
        <Img src={staticFile('cases/news/briefing-reader.png')} style={{width: '100%', height: '100%', objectFit: 'contain', objectPosition: 'center', background: theme.paper}} />
        <div style={{position: 'absolute', left: 14, bottom: 14}}><SourceBadge>REAL BRIEFING</SourceBadge></div>
      </div>
      <div style={{position: 'absolute', left: 430, right: 76, top: 440, display: 'flex', flexDirection: 'column', gap: 18}}>
        {manifest.news_briefing.items.map((item, i) => {
          const enter = interpolate(frame, [10 + i * 18, 24 + i * 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <div key={item.id} style={{border: '1px solid rgba(7,17,23,.24)', background: 'rgba(255,255,255,.66)', padding: '22px 22px 20px', transform: `translateX(${(1 - enter) * 42}px)`, opacity: enter}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                <span style={{fontFamily: theme.fontMono, color: '#4D8235', fontSize: 18}}>{item.id} · {item.category}</span>
                <SourceBadge>{item.preprint ? 'PREPRINT' : 'VERIFIED'}</SourceBadge>
              </div>
              <div style={{fontFamily: theme.fontSans, fontSize: 28, fontWeight: 900, lineHeight: 1.27, marginTop: 14}}>{item.title_zh}</div>
              <div style={{fontFamily: theme.fontMono, fontSize: 17, marginTop: 14, opacity: .72}}>{item.source} · {item.date}</div>
            </div>
          );
        })}
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 1240, background: theme.ink, color: theme.paper, padding: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <span style={{fontFamily: theme.fontMono, fontSize: 19}}>daily_pipeline_manifest_2026-07-13.json</span>
        <SourceBadge>COMPLETE · COMMITTED</SourceBadge>
      </div>
      <div style={{position: 'absolute', left: 76, bottom: 188, fontFamily: theme.fontMono, fontSize: 17}}>AI HOT = DISCOVERY ONLY · OFFICIAL HTTPS SOURCES = EVIDENCE</div>
    </div>
  );
};
