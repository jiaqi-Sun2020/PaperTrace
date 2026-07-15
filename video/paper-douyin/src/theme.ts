export const theme = {
  ink: '#071117',
  inkSoft: '#0F2028',
  paper: '#F0EDE5',
  paperMuted: '#C8C7BE',
  signal: '#70B84C',
  signalLight: '#A3D47D',
  warning: '#F1C453',
  white: '#FFFFFF',
  line: 'rgba(240,237,229,0.18)',
  lineStrong: 'rgba(240,237,229,0.42)',
  fontSans: '"Microsoft YaHei UI", "Noto Sans CJK SC", Arial, sans-serif',
  fontCondensed: '"Arial Narrow", "Microsoft YaHei UI", Arial, sans-serif',
  fontMono: 'Consolas, "SFMono-Regular", monospace',
  safeX: 76,
  safeTop: 156,
  safeBottom: 286,
} as const;

export const clamp = (value: number, min = 0, max = 1) =>
  Math.max(min, Math.min(max, value));
