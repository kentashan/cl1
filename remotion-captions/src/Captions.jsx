import {
  AbsoluteFill,
  Img,
  useCurrentFrame,
  useVideoConfig,
  staticFile,
  interpolate,
  Audio,
} from "remotion";

// 各画像の表示区間（動画と同じ: 各3秒、フェード1秒）
// 総フレーム数480 = 16秒 × 30fps
// xfade: offset=3,6,9,12 → img1:0-4s, img2:3-7s (overlap 3-4s), ...
const IMAGES = [
  { file: "converted1.png", start: 0,   end: 4   },
  { file: "converted2.png", start: 3,   end: 7   },
  { file: "converted3.png", start: 6,   end: 10  },
  { file: "converted4.png", start: 9,   end: 13  },
  { file: "converted5.png", start: 12,  end: 16  },
];

const CAPTIONS = [
  { start: 0.00, end: 1.24, text: "白い雪" },
  { start: 2.32, end: 3.94, text: "二人の冬" },
  { start: 5.14, end: 6.62, text: "肩と肩" },
  { start: 6.90, end: 9.98, text: "触れたままで" },
  { start: 10.28, end: 12.68, text: "寒いねと" },
  { start: 13.52, end: 15.98, text: "笑うたび少し" },
];

const FADE_DURATION = 1.0;  // 画像フェード秒数
const TEXT_FADE = 0.3;      // テキストフェード秒数

const fontFaceStyle = `
  @font-face {
    font-family: 'Yomogi';
    src: url('/Yomogi-Regular.ttf') format('truetype');
    font-weight: normal;
    font-style: normal;
  }
`;

export const CaptionVideo = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  // テキストopacity
  const activeCaption = CAPTIONS.find((c) => t >= c.start && t <= c.end);
  let textOpacity = 0;
  if (activeCaption) {
    const elapsed = t - activeCaption.start;
    const remaining = activeCaption.end - t;
    textOpacity = Math.min(
      interpolate(elapsed,   [0, TEXT_FADE], [0, 1], { extrapolateRight: "clamp" }),
      interpolate(remaining, [0, TEXT_FADE], [0, 1], { extrapolateRight: "clamp" })
    );
  }

  return (
    <AbsoluteFill style={{ background: "black", overflow: "hidden" }}>
      <style>{fontFaceStyle}</style>

      {/* 画像レイヤー（フェード＋スケールアニメーション） */}
      {IMAGES.map(({ file, start, end }) => {
        if (t < start || t > end) return null;
        const elapsed = t - start;
        const remaining = end - t;

        const imgOpacity = Math.min(
          interpolate(elapsed,   [0, FADE_DURATION], [0, 1], { extrapolateRight: "clamp" }),
          interpolate(remaining, [0, FADE_DURATION], [0, 1], { extrapolateRight: "clamp" })
        );

        // スケール: 表示開始→終了で 100% → 110%
        const duration = end - start;
        const scale = interpolate(elapsed, [0, duration], [1.00, 1.10], {
          extrapolateRight: "clamp",
        });

        return (
          <AbsoluteFill
            key={file}
            style={{
              opacity: imgOpacity,
              transform: `scale(${scale})`,
              transformOrigin: "center center",
            }}
          >
            <Img
              src={staticFile(file)}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </AbsoluteFill>
        );
      })}

      {/* BGM音声 */}
      <Audio src={staticFile("output_with_bgm.webm")} />

      {/* 歌詞テロップ（中央・フェードイン/アウト） */}
      {activeCaption && (
        <AbsoluteFill
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            paddingTop: 120,
          }}
        >
          <div
            style={{
              fontFamily: "'Yomogi', cursive",
              fontSize: 56,
              color: "white",
              textShadow:
                "2px 2px 8px rgba(0,0,0,0.9), -1px -1px 4px rgba(0,0,0,0.7), 0 0 16px rgba(0,0,0,0.6)",
              letterSpacing: "0.08em",
              textAlign: "center",
              padding: "12px 32px",
              opacity: textOpacity,
            }}
          >
            {activeCaption.text}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
