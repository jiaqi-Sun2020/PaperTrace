import {AbsoluteFill, Img, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';
import manifest from '../data/case-manifest.json';
import {theme} from '../theme';

const fragmentStyle: React.CSSProperties = {
  position: 'absolute', overflow: 'hidden', border: `1px solid ${theme.lineStrong}`,
  background: theme.paper, boxShadow: '0 25px 60px rgba(0,0,0,.28)',
};

const problemStart = 131;
const methodStart = 279;
const problemShotDurations = [49, 49, 50] as const;
const shotDuration = 45;

const ShotShell: React.FC<{
  eyebrow: string;
  index: string;
  total?: string;
  durationInFrames?: number;
  accent?: string;
  children: React.ReactNode;
}> = ({eyebrow, index, total = '04', durationInFrames = shotDuration, accent = theme.signal, children}) => {
  const frame = useCurrentFrame();
  const lift = interpolate(frame, [0, 12], [34, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{background: theme.ink, color: theme.paper}}>
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(240,237,229,.055) 1px, transparent 1px), linear-gradient(90deg, rgba(240,237,229,.055) 1px, transparent 1px)', backgroundSize: '72px 72px'}} />
      <div style={{position: 'absolute', left: 76, right: 76, top: 156, display: 'flex', justifyContent: 'space-between', fontFamily: theme.fontMono, fontSize: 19, letterSpacing: 2}}>
        <span style={{color: accent}}>{eyebrow}</span>
        <span>{index} / {total}</span>
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, top: 245, bottom: 430, translate: `0 ${lift}px`}}>
        {children}
      </div>
      <div style={{position: 'absolute', left: 76, right: 76, bottom: 382, height: 3, background: 'rgba(240,237,229,.14)'}}>
        <div style={{width: `${interpolate(frame, [0, durationInFrames - 1], [4, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}%`, height: '100%', background: accent}} />
      </div>
    </AbsoluteFill>
  );
};

const ProblemSeenShot: React.FC = () => {
  const frame = useCurrentFrame();
  const cards = [
    {label: 'PaperTrace', meta: 'SOURCE PDF', image: 'cases/paper/source-page-1.png'},
    {label: 'NEWS', meta: 'DAILY BRIEFING', image: 'cases/news/briefing-reader.png'},
    {label: 'DIALOGUE', meta: 'REVIEWABLE FEEDBACK', image: null},
  ];
  return (
    <ShotShell eyebrow="THE REAL PROBLEM / EXPOSURE" index="01" total="03" durationInFrames={problemShotDurations[0]} accent={theme.warning}>
      <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 82, lineHeight: 1.02}}>看过，不等于留下。</div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18, marginTop: 72}}>
        {cards.map((card, index) => {
          const enter = interpolate(frame, [index * 5, index * 5 + 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <div key={card.label} style={{height: 650, border: `1px solid ${theme.lineStrong}`, background: theme.inkSoft, overflow: 'hidden', opacity: enter, translate: `0 ${(1 - enter) * 36}px`}}>
              <div style={{height: 440, position: 'relative', background: card.image ? theme.paper : 'linear-gradient(145deg, rgba(112,184,76,.08), rgba(15,32,40,.96))'}}>
                {card.image ? <Img src={staticFile(card.image)} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} /> : (
                  <div style={{padding: '62px 24px', fontFamily: theme.fontMono, color: theme.paperMuted, fontSize: 19, lineHeight: 2.2}}>concepts<br/>events<br/>sources<br/>review_queue</div>
                )}
                <div style={{position: 'absolute', left: 18, top: 18, padding: '8px 11px', background: theme.ink, color: theme.warning, fontFamily: theme.fontMono, fontSize: 16}}>VIEWED</div>
              </div>
              <div style={{padding: '25px 22px'}}>
                <div style={{fontFamily: theme.fontMono, color: theme.warning, fontSize: 19}}>{card.label}</div>
                <div style={{fontFamily: theme.fontMono, fontSize: 18, marginTop: 16, color: theme.paperMuted}}>{card.meta}</div>
              </div>
            </div>
          );
        })}
      </div>
    </ShotShell>
  );
};

const ProblemDisconnectedShot: React.FC = () => {
  const frame = useCurrentFrame();
  const pulse = interpolate(frame, [0, 24, 48], [0.35, 1, 0.35], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <ShotShell eyebrow="THE REAL PROBLEM / DISCONNECTED" index="02" total="03" durationInFrames={problemShotDurations[1]} accent={theme.warning}>
      <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 82, lineHeight: 1.02}}>入口很多，连接却断了。</div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 185px 1fr', alignItems: 'center', marginTop: 95}}>
        <div style={{display: 'grid', gap: 24}}>
          {['论文 / PDF', '新闻 / BRIEFING', '对话 / FEEDBACK'].map((label) => (
            <div key={label} style={{border: `1px solid ${theme.lineStrong}`, background: theme.inkSoft, padding: '31px 28px', fontFamily: theme.fontMono, fontWeight: 800, fontSize: 25}}>{label}</div>
          ))}
        </div>
        <svg width="185" height="500" viewBox="0 0 185 500" aria-hidden="true">
          <path d="M0 82 H70 M115 82 H185 M0 250 H70 M115 250 H185 M0 418 H70 M115 418 H185" fill="none" stroke={theme.paperMuted} strokeWidth="3" strokeDasharray="12 10" opacity={0.55} />
          <path d="M78 66 L108 98 M108 66 L78 98 M78 234 L108 266 M108 234 L78 266 M78 402 L108 434 M108 402 L78 434" fill="none" stroke={theme.warning} strokeWidth="5" opacity={pulse} />
        </svg>
        <div style={{height: 500, display: 'flex', alignItems: 'center'}}>
          <div style={{width: '100%', border: `1px dashed ${theme.lineStrong}`, background: 'rgba(240,237,229,.025)', padding: '66px 20px', textAlign: 'center'}}>
            <div style={{fontFamily: theme.fontMono, color: theme.paperMuted, fontSize: 18}}>SHARED CONTEXT</div>
            <div style={{fontFamily: theme.fontCondensed, color: theme.warning, fontWeight: 950, fontSize: 92, marginTop: 20}}>?</div>
            <div style={{fontFamily: theme.fontMono, color: theme.warning, fontSize: 18, marginTop: 12}}>NOT CONNECTED</div>
          </div>
        </div>
      </div>
    </ShotShell>
  );
};

const ProblemStateShot: React.FC = () => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [4, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <ShotShell eyebrow="THE REAL PROBLEM / MEMORY GAP" index="03" total="03" durationInFrames={problemShotDurations[2]} accent={theme.warning}>
      <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 82, lineHeight: 1.02}}>信息都在，却串不起来。</div>
      <div style={{marginTop: 120, borderTop: `1px solid ${theme.lineStrong}`, borderBottom: `1px solid ${theme.lineStrong}`, padding: '68px 0 74px', textAlign: 'center'}}>
        <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 30, opacity: reveal, scale: 0.9 + reveal * 0.1}}>
          <span style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 86}}>SEEN</span>
          <span style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 100, color: theme.warning}}>≠</span>
          <span style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 86}}>MASTERED</span>
        </div>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginTop: 52}}>
        {['NO SOURCE LINK', 'FRAGMENTED CONTEXT', 'NO MEMORY UPDATE'].map((label, index) => (
          <div key={label} style={{border: `1px solid rgba(241,196,83,${0.3 + reveal * 0.7})`, background: 'rgba(241,196,83,.055)', padding: '23px 14px', textAlign: 'center', fontFamily: theme.fontMono, color: theme.warning, fontSize: 18, opacity: interpolate(frame, [16 + index * 5, 24 + index * 5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>{label}</div>
        ))}
      </div>
    </ShotShell>
  );
};

const MethodPaperShot: React.FC = () => (
  <ShotShell eyebrow="RESEARCH METHOD / SOURCE" index="01">
    <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 80, lineHeight: 1.02}}>先回到真实来源。</div>
    <div style={{position: 'absolute', left: 0, right: 0, top: 160, height: 760, overflow: 'hidden', border: `1px solid ${theme.lineStrong}`, background: theme.paper}}>
      <Img src={staticFile('cases/paper/fig3-circuit-depth.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'center'}} />
      <div style={{position: 'absolute', left: 24, top: 24, padding: '11px 15px', background: theme.ink, color: theme.signalLight, fontFamily: theme.fontMono, fontSize: 18}}>SOURCE PAGE 03 · REAL FIGURE</div>
    </div>
  </ShotShell>
);

const MethodNewsShot: React.FC = () => (
  <ShotShell eyebrow="RESEARCH METHOD / VERIFY" index="02">
    <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 80, lineHeight: 1.02}}>再核对证据与日期。</div>
    <div style={{position: 'absolute', left: 0, right: 0, top: 160, height: 760, overflow: 'hidden', border: `1px solid ${theme.lineStrong}`, background: theme.paper}}>
      <Img src={staticFile('cases/news/briefing-reader.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} />
      <div style={{position: 'absolute', left: 24, right: 24, bottom: 24, padding: '18px 20px', background: 'rgba(7,17,23,.94)', color: theme.paper}}>
        <div style={{fontFamily: theme.fontMono, color: theme.signalLight, fontSize: 18}}>VERIFIED BRIEFING · {manifest.news_briefing.date_range}</div>
        <div style={{fontFamily: theme.fontSans, fontWeight: 900, fontSize: 29, lineHeight: 1.3, marginTop: 8}}>{manifest.news_briefing.items[0].source} · {manifest.news_briefing.items[0].date}</div>
      </div>
    </div>
  </ShotShell>
);

const SkillShot: React.FC = () => {
  const frame = useCurrentFrame();
  const skills = ['reader-skill', 'ai-quantum-news-briefing', 'reader-learner'];
  return (
    <ShotShell eyebrow="METHOD → REUSABLE SKILL" index="03">
      <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 78, lineHeight: 1.04}}>把方法，封装成 skill。</div>
      <div style={{display: 'grid', gap: 18, marginTop: 90}}>
        {skills.map((skill, index) => {
          const enter = interpolate(frame, [6 + index * 7, 15 + index * 7], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          return (
            <div key={skill} style={{display: 'grid', gridTemplateColumns: '76px 1fr auto', alignItems: 'center', gap: 20, padding: '27px 28px', border: `1px solid ${theme.lineStrong}`, background: 'rgba(15,32,40,.92)', opacity: enter, translate: `${(1 - enter) * 42}px 0`}}>
              <span style={{fontFamily: theme.fontMono, color: theme.signal, fontSize: 22}}>0{index + 1}</span>
              <span style={{fontFamily: theme.fontMono, fontWeight: 800, fontSize: 27}}>{skill}</span>
              <span style={{fontFamily: theme.fontMono, color: theme.signalLight, fontSize: 18}}>READY</span>
            </div>
          );
        })}
      </div>
      <div style={{marginTop: 42, fontFamily: theme.fontSans, color: theme.paperMuted, fontSize: 34}}>同一套规则，可以重复执行，也可以逐步验证。</div>
    </ShotShell>
  );
};

const PipelineShot: React.FC = () => {
  const frame = useCurrentFrame();
  const inputs = [
    ['01', 'PaperTrace', 'PDF → Reader'],
    ['02', 'NEWS', 'Source → Briefing'],
    ['03', 'FEEDBACK', 'Review → Memory'],
  ];
  return (
    <ShotShell eyebrow="SKILL → PIPELINE" index="04">
      <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 76, lineHeight: 1.04}}>三条入口，一套 pipeline。</div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 76px 1fr', alignItems: 'center', marginTop: 78}}>
        <div style={{display: 'grid', gap: 18}}>
          {inputs.map(([index, title, meta], itemIndex) => {
            const enter = interpolate(frame, [4 + itemIndex * 6, 13 + itemIndex * 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
            return (
              <div key={title} style={{border: `1px solid ${theme.lineStrong}`, background: theme.inkSoft, padding: '23px 24px', opacity: enter, translate: `${(1 - enter) * -30}px 0`}}>
                <div style={{display: 'flex', justifyContent: 'space-between', fontFamily: theme.fontMono, fontSize: 18, color: theme.signalLight}}><span>{index}</span><span>{title}</span></div>
                <div style={{fontFamily: theme.fontMono, fontSize: 21, marginTop: 13}}>{meta}</div>
              </div>
            );
          })}
        </div>
        <svg width="76" height="520" viewBox="0 0 76 520" aria-hidden="true">
          <path d="M2 90 H38 V260 H72" fill="none" stroke={theme.signal} strokeWidth="3" />
          <path d="M2 260 H72" fill="none" stroke={theme.signal} strokeWidth="3" />
          <path d="M2 430 H38 V260" fill="none" stroke={theme.signal} strokeWidth="3" />
        </svg>
        <div style={{height: 520, display: 'flex', alignItems: 'center'}}>
          <div style={{width: '100%', border: `2px solid ${theme.signal}`, background: 'rgba(112,184,76,.1)', padding: '44px 28px', textAlign: 'center', scale: interpolate(frame, [19, 31], [0.88, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
            <div style={{fontFamily: theme.fontMono, color: theme.signalLight, fontSize: 18}}>VISIBLE WIKI</div>
            <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 50, lineHeight: 1.05, marginTop: 18}}>ONE<br/>MEMORY</div>
            <div style={{fontFamily: theme.fontMono, fontSize: 17, color: theme.paperMuted, marginTop: 22}}>TRACEABLE · REVIEWABLE</div>
          </div>
        </div>
      </div>
    </ShotShell>
  );
};

export const RealHookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = interpolate(frame, [0, 75], [0, -38], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div style={{position: 'absolute', inset: 0, background: theme.ink, opacity, overflow: 'hidden'}}>
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(240,237,229,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(240,237,229,.05) 1px, transparent 1px)', backgroundSize: '72px 72px'}} />
      <div style={{...fragmentStyle, left: 55, top: 180 + drift, width: 650, height: 700, transform: 'rotate(-4deg)'}}>
        <Img src={staticFile('cases/paper/source-page-1.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} />
      </div>
      <div style={{...fragmentStyle, right: 48, top: 410 - drift * .4, width: 470, height: 600, transform: 'rotate(4deg)'}}>
        <Img src={staticFile('cases/news/briefing-reader.png')} style={{width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top'}} />
      </div>
      <div style={{...fragmentStyle, left: 85, top: 1030 + drift * .3, width: 500, height: 265, padding: 28, background: theme.inkSoft, color: theme.paper, transform: 'rotate(2deg)'}}>
        <div style={{fontFamily: theme.fontMono, color: theme.signalLight, fontSize: 18}}>VERIFIED NEWS · {manifest.news_briefing.items[0].date}</div>
        <div style={{fontFamily: theme.fontSans, fontWeight: 900, fontSize: 31, lineHeight: 1.25, marginTop: 16}}>{manifest.news_briefing.items[0].title_zh}</div>
      </div>
      <div style={{...fragmentStyle, right: 70, top: 1315 - drift * .2, width: 520, height: 270, padding: 28, background: theme.paper, color: theme.ink, transform: 'rotate(-3deg)'}}>
        <div style={{fontFamily: theme.fontMono, color: '#4D7E35', fontSize: 18}}>REVIEWABLE FEEDBACK · SCHEMA ONLY</div>
        <div style={{fontFamily: theme.fontMono, fontSize: 27, lineHeight: 1.8, marginTop: 12}}>concepts · events<br/>sources · review_queue</div>
      </div>
      <div style={{position: 'absolute', left: 76, top: 156, right: 76, color: theme.paper, fontFamily: theme.fontMono, fontSize: 18, letterSpacing: 2}}>REAL REPOSITORY ARTIFACTS / 01</div>
      <Sequence from={problemStart} durationInFrames={methodStart - problemStart + shotDuration * 4} premountFor={15}>
        <AbsoluteFill style={{background: theme.ink}}>
          <Sequence from={0} durationInFrames={problemShotDurations[0]} premountFor={15}><ProblemSeenShot /></Sequence>
          <Sequence from={problemShotDurations[0]} durationInFrames={problemShotDurations[1]} premountFor={15}><ProblemDisconnectedShot /></Sequence>
          <Sequence from={problemShotDurations[0] + problemShotDurations[1]} durationInFrames={problemShotDurations[2]} premountFor={15}><ProblemStateShot /></Sequence>
          <Sequence from={methodStart - problemStart} durationInFrames={shotDuration} premountFor={15}><MethodPaperShot /></Sequence>
          <Sequence from={methodStart - problemStart + shotDuration} durationInFrames={shotDuration} premountFor={15}><MethodNewsShot /></Sequence>
          <Sequence from={methodStart - problemStart + shotDuration * 2} durationInFrames={shotDuration} premountFor={15}><SkillShot /></Sequence>
          <Sequence from={methodStart - problemStart + shotDuration * 3} durationInFrames={shotDuration} premountFor={15}><PipelineShot /></Sequence>
        </AbsoluteFill>
      </Sequence>
    </div>
  );
};
