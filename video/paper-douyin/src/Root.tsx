import {Composition} from 'remotion';
import timeline from './data/audio-timeline.json';
import {PaperTrace} from './PaperTrace';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="PaperTrace"
    component={PaperTrace}
    durationInFrames={timeline.durationInFrames}
    fps={timeline.fps}
    width={1080}
    height={1920}
  />
);
