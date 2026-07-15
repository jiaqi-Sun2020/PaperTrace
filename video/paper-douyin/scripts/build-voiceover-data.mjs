import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sourceDirectory = path.join(projectRoot, 'video');
const publicDirectory = path.join(projectRoot, 'public', 'audio');
const dataDirectory = path.join(projectRoot, 'src', 'data');
const voiceover = fs.readFileSync(path.join(projectRoot, 'voiceover.md'), 'utf8');
const fps = 30;
const trackIds = ['hook', 'reveal', 'paper', 'bridge', 'news', 'memory', 'outro'];

const normalize = (text) => text.replace(/[\s`]/g, '').toLowerCase();
const countCharacters = (text) => Array.from(text.replace(/[\s`]/g, '')).length;

const splitCaptionText = (text) => {
  const sentences = text.match(/[^。！？；]+[。！？；]?/gu) ?? [text];
  const pieces = sentences.flatMap((sentence) => {
    if (countCharacters(sentence) <= 28) return [sentence];
    return sentence.match(/[^，：]+[，：]?/gu) ?? [sentence];
  });
  const captions = [];
  let current = '';
  for (const piece of pieces) {
    if (!current || countCharacters(current + piece) <= 28) {
      current += piece;
    } else {
      captions.push(current);
      current = piece;
    }
  }
  if (current) captions.push(current);
  const cleaned = captions.map((caption) => caption.trim()).filter(Boolean);
  const merged = [];
  for (let index = 0; index < cleaned.length; index++) {
    if (countCharacters(cleaned[index]) <= 7 && index < cleaned.length - 1) {
      cleaned[index + 1] = `${cleaned[index]}${cleaned[index + 1]}`;
    } else {
      merged.push(cleaned[index]);
    }
  }
  return merged;
};

const getWavDuration = (filePath) => {
  const buffer = fs.readFileSync(filePath);
  if (buffer.toString('ascii', 0, 4) !== 'RIFF' || buffer.toString('ascii', 8, 12) !== 'WAVE') {
    throw new Error(`Not a RIFF/WAVE file: ${filePath}`);
  }
  let offset = 12;
  let byteRate = 0;
  let dataSize = 0;
  while (offset + 8 <= buffer.length) {
    const id = buffer.toString('ascii', offset, offset + 4);
    const size = buffer.readUInt32LE(offset + 4);
    if (id === 'fmt ') byteRate = buffer.readUInt32LE(offset + 16);
    if (id === 'data') dataSize = size;
    offset += 8 + size + (size % 2);
  }
  if (!byteRate || !dataSize) throw new Error(`Missing WAV fmt/data chunk: ${filePath}`);
  return dataSize / byteRate;
};

fs.mkdirSync(publicDirectory, {recursive: true});

const numberedFiles = fs.readdirSync(sourceDirectory)
  .filter((name) => /^\d+.*\.wav$/iu.test(name))
  .map((name) => {
    const match = name.match(/^(\d+)(.*)\.wav$/iu);
    return {name, order: Number(match[1]), text: match[2]};
  })
  .sort((a, b) => a.order - b.order);

if (numberedFiles.length !== trackIds.length) {
  throw new Error(`Expected ${trackIds.length} numbered WAV files, found ${numberedFiles.length}`);
}
numberedFiles.forEach((file, index) => {
  if (file.order !== index) throw new Error(`Expected WAV prefix ${index}, found ${file.order}`);
  if (!normalize(voiceover).includes(normalize(file.text))) {
    throw new Error(`voiceover.md does not contain track ${index}: ${file.text}`);
  }
});

let frameCursor = 0;
const captions = [];
const tracks = numberedFiles.map((source, index) => {
  const id = trackIds[index];
  const sourcePath = path.join(sourceDirectory, source.name);
  const publicName = `track-${index}.wav`;
  const publicPath = path.join(publicDirectory, publicName);
  fs.copyFileSync(sourcePath, publicPath);

  const durationSeconds = getWavDuration(publicPath);
  const durationFrames = Math.ceil(durationSeconds * fps);
  const startFrame = frameCursor;
  const endFrame = startFrame + durationFrames;
  const startMs = startFrame / fps * 1000;
  const endMs = endFrame / fps * 1000;
  const segments = splitCaptionText(source.text);
  const weights = segments.map(countCharacters);
  const totalWeight = weights.reduce((sum, weight) => sum + weight, 0);
  let segmentCursor = startMs;

  segments.forEach((text, segmentIndex) => {
    const segmentEnd = segmentIndex === segments.length - 1
      ? endMs
      : segmentCursor + (endMs - startMs) * weights[segmentIndex] / totalWeight;
    captions.push({
      text,
      startMs: Math.round(segmentCursor),
      endMs: Math.round(segmentEnd),
      timestampMs: null,
      confidence: null,
    });
    segmentCursor = segmentEnd;
  });

  frameCursor = endFrame;
  return {
    id,
    order: index,
    sourceFilename: source.name,
    publicFile: `audio/${publicName}`,
    captionText: source.text,
    durationSeconds: Number(durationSeconds.toFixed(6)),
    startFrame,
    durationFrames,
    endFrame,
    startMs: Math.round(startMs),
    endMs: Math.round(endMs),
  };
});

const timeline = {
  projectName: 'PaperTrace',
  compositionId: 'PaperTrace',
  fps,
  durationInFrames: frameCursor,
  durationSeconds: Number((frameCursor / fps).toFixed(3)),
  source: 'voiceover.md and numbered WAV basenames in video/',
  tracks,
};

fs.writeFileSync(path.join(dataDirectory, 'audio-timeline.json'), `${JSON.stringify(timeline, null, 2)}\n`);
fs.writeFileSync(path.join(dataDirectory, 'captions.json'), `${JSON.stringify(captions, null, 2)}\n`);

console.log(`PaperTrace: ${tracks.length} tracks, ${captions.length} captions, ${frameCursor} frames (${timeline.durationSeconds}s)`);
for (const track of tracks) console.log(`${track.order}/${track.id}: ${track.startFrame}-${track.endFrame} / ${track.durationSeconds}s`);
