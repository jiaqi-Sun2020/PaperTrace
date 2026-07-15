import {interpolate, useCurrentFrame} from 'remotion';
import {KnowledgeNode} from '../components/KnowledgeNode';
import {SourceBadge} from '../components/SourceBadge';
import {theme} from '../theme';

export const ConnectionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const line = interpolate(frame, [12, 56], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div style={{position: 'absolute', inset: 0, background: theme.ink, color: theme.paper, overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 76, top: 150, right: 76}}>
        <div style={{fontFamily: theme.fontMono, color: theme.signalLight, fontSize: 19}}>NO INVENTED LINK / SHARED MEMORY</div>
        <div style={{fontFamily: theme.fontCondensed, fontWeight: 950, fontSize: 65, marginTop: 18, lineHeight: 1.08}}>不是强行关联。<br/>是共同进入记忆。</div>
      </div>
      <svg width="1080" height="1920" style={{position: 'absolute', inset: 0}}>
        <line x1="230" y1="800" x2={230 + 310 * line} y2={800 + 210 * line} stroke={theme.signal} strokeWidth="3" />
        <line x1="850" y1="800" x2={850 - 310 * line} y2={800 + 210 * line} stroke={theme.signal} strokeWidth="3" />
        <line x1="540" y1="1250" x2="540" y2={1250 - 230 * line} stroke={theme.signal} strokeWidth="3" />
      </svg>
      <KnowledgeNode label="真实论文" x={165} y={740} delay={0} size={132} />
      <KnowledgeNode label="已验证新闻" x={783} y={740} delay={6} size={132} />
      <KnowledgeNode label="明确反馈" x={474} y={1210} delay={12} size={132} />
      <KnowledgeNode label="PaperTraceTRACE\nMEMORY" x={447} y={910} delay={36} size={186} />
      <div style={{position: 'absolute', left: 76, right: 76, top: 1390, border: `1px solid ${theme.lineStrong}`, padding: 28, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <div style={{fontFamily: theme.fontSans, fontSize: 27, lineHeight: 1.45}}>所选案例之间未发现直接引用或因果关系。</div>
        <SourceBadge>SHARED-MEMORY-ONLY</SourceBadge>
      </div>
    </div>
  );
};
