import {Audio} from '@remotion/media';
import {AbsoluteFill, Sequence, staticFile} from 'remotion';
import {SafeSubtitle} from './components/SafeSubtitle';
import timeline from './data/audio-timeline.json';
import {ConnectionScene} from './scenes/ConnectionScene';
import {MemoryScene} from './scenes/MemoryScene';
import {OutroScene} from './scenes/OutroScene';
import {ProductRevealScene} from './scenes/ProductRevealScene';
import {RealHookScene} from './scenes/RealHookScene';
import {RealNewsScene} from './scenes/RealNewsScene';
import {RealPaperScene} from './scenes/RealPaperScene';
import {theme} from './theme';

const sceneByTrack = {
  hook: RealHookScene,
  reveal: ProductRevealScene,
  paper: RealPaperScene,
  bridge: ConnectionScene,
  news: RealNewsScene,
  memory: MemoryScene,
  outro: OutroScene,
} as const;

export const PaperTrace: React.FC = () => (
  <AbsoluteFill style={{backgroundColor: theme.ink}}>
    {timeline.tracks.map((track) => {
      const Scene = sceneByTrack[track.id as keyof typeof sceneByTrack];
      return (
        <Sequence
          key={`scene-${track.id}`}
          from={track.startFrame}
          durationInFrames={track.durationFrames}
          premountFor={30}
        >
          <Scene />
        </Sequence>
      );
    })}

    {timeline.tracks.map((track) => (
      <Sequence
        key={`audio-${track.id}`}
        from={track.startFrame}
        durationInFrames={track.durationFrames}
        layout="none"
      >
        <Audio src={staticFile(track.publicFile)} />
      </Sequence>
    ))}
    <SafeSubtitle />
  </AbsoluteFill>
);
