import { Composition } from "remotion";
import { CaptionVideo } from "./Captions";

export const RemotionRoot = () => {
  return (
    <Composition
      id="CaptionVideo"
      component={CaptionVideo}
      durationInFrames={480}
      fps={30}
      width={786}
      height={786}
    />
  );
};
