import { AbsoluteFill, OffthreadVideo, useCurrentFrame, useVideoConfig, staticFile } from "remotion";

const CAPTIONS = [
  { start: 0.00, end: 4.06, text: "二人の冬" },
  { start: 5.14, end: 6.62, text: "肩と肩" },
  { start: 6.90, end: 9.98, text: "触れたままで" },
  { start: 10.28, end: 12.68, text: "寒いねと" },
  { start: 13.52, end: 15.98, text: "笑うたび少し" },
];

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
  const currentTime = frame / fps;

  const activeCaption = CAPTIONS.find(
    (c) => currentTime >= c.start && currentTime <= c.end
  );

  return (
    <AbsoluteFill>
      <style>{fontFaceStyle}</style>
      <OffthreadVideo
        src={staticFile("output_with_bgm.webm")}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
      />
      {activeCaption && (
        <AbsoluteFill
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "center",
            paddingBottom: 60,
          }}
        >
          <div
            style={{
              fontFamily: "'Yomogi', cursive",
              fontSize: 52,
              color: "white",
              textShadow:
                "2px 2px 8px rgba(0,0,0,0.9), -1px -1px 4px rgba(0,0,0,0.7), 0 0 12px rgba(0,0,0,0.5)",
              letterSpacing: "0.05em",
              textAlign: "center",
              padding: "8px 24px",
            }}
          >
            {activeCaption.text}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
