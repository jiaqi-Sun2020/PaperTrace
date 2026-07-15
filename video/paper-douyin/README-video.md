# PaperTrace 抖音竖屏产品视频

## 交付规格

- Composition ID：`PaperTrace`
- 画面：1080 × 1920，30 FPS，2374 帧，79.133 秒
- 编码：H.264 / yuv420p MP4
- 语言：中文配音与同步画面字幕
- 音频：7 段本地 WAV 旁白，无背景音乐

最终 ffprobe 结果：视频流 H.264，1080 × 1920，30 FPS，2374 帧，79.133333 秒；AAC 音频为 48 kHz 双声道，79.168 秒；容器 79.168 秒。

## 旁白与字幕来源

- 人工修改后的旁白：`voiceover.md`（生成脚本只读，不覆盖）
- 原始音轨：`video/*.wav`，文件名即对应完整旁白文本
- 渲染音轨副本：`public/audio/track-0.wav` 至 `track-6.wav`
- 音频时间轴：`src/data/audio-timeline.json`
- 字幕：`src/data/captions.json`，按每段 WAV 的真实时长和句子字数比例生成

## 时间线

- 00:00–00:15.30：真实信息过载与研究问题
- 00:15.30–00:25.13：PaperTrace 产品揭示
- 00:25.13–00:34.33：真实论文案例
- 00:34.33–00:44.33：个人知识库与资讯桥接
- 00:44.33–00:56.13：真实新闻案例
- 00:56.13–01:11.40：反馈进入记忆
- 01:11.40–01:19.13：结束画面

## 如何运行

在目录 `D:\AI\PaperTrace\video\paper-douyin` 执行：

```powershell
npm.cmd run build:voiceover
npm.cmd run typecheck
npx.cmd remotion compositions
npx.cmd remotion studio
```

完整渲染：

```powershell
npx.cmd remotion render PaperTrace out\papertrace.mp4 --codec=h264 --pixel-format=yuv420p
```

关键静帧：

```powershell
npx.cmd remotion still PaperTrace out\check-papertrace-hook-v2.png --frame=300
npx.cmd remotion still PaperTrace out\check-papertrace-paper-v2.png --frame=900
npx.cmd remotion still PaperTrace out\check-papertrace-news-v2.png --frame=1500
npx.cmd remotion still PaperTrace out\check-papertrace-memory-v2.png --frame=1900
npx.cmd remotion still PaperTrace out\papertrace-cover.png --frame=2300
```

媒体参数检查：

```powershell
npx.cmd remotion ffprobe out\papertrace.mp4
```

## 数据边界

所有事实仍来自 `src/data/case-manifest.json`。视频不读取 learner profile 私人内容，也不展示原始私人反馈。新闻证据截图使用核验 manifest 的 UTF-8 字段修复原 artifact 的历史编码乱码，源文件未修改。

## 已执行验证

- `npm.cmd run build:voiceover`：7 tracks，21 captions，2374 frames
- `npm.cmd run typecheck`：通过
- `npx.cmd remotion compositions`：`PaperTrace` / 1080 × 1920 / 30 FPS / 2374 frames
- 五个关键静帧：延长后的开场、论文、新闻、反馈、封面均通过人工检查
- 完整渲染：`out/papertrace.mp4`
- ffprobe：H.264 + AAC，视频 79.133333 秒，音频 79.168 秒
- `silencedetect`：未检测到超过 1 秒的异常静音
