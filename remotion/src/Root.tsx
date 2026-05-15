import { Composition } from "remotion";
import { HoogMap, hoogMapSchema } from "./compositions/HoogMap";
import { HoogScene, hoogSceneSchema } from "./compositions/HoogScene";
import { HoogTypography, hoogTypographySchema } from "./compositions/HoogTypography";
import { Thumbnail, thumbnailSchema } from "./compositions/Thumbnail";

// 9:16 vertical, 30 fps, up to 180 sec (Shorts limit enforced at upload)
const WIDTH = 1080;
const HEIGHT = 1920;
const FPS = 30;
const MAX_FRAMES = 180 * FPS;

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="HoogScene"
        component={HoogScene}
        durationInFrames={MAX_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        schema={hoogSceneSchema}
        defaultProps={{
          title: "The Story Begins",
          captions: [],
          scenes: [],
          audioSrc: null,
        }}
      />
      <Composition
        id="HoogMap"
        component={HoogMap}
        durationInFrames={MAX_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        schema={hoogMapSchema}
        defaultProps={{
          title: "The Story Begins",
          captions: [],
          audioSrc: null,
          focusRegion: "europe",
        }}
      />
      <Composition
        id="HoogTypography"
        component={HoogTypography}
        durationInFrames={MAX_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        schema={hoogTypographySchema}
        defaultProps={{
          title: "A Bold Claim",
          captions: [],
          audioSrc: null,
        }}
      />
      <Composition
        id="Thumbnail"
        component={Thumbnail}
        durationInFrames={1}
        fps={30}
        width={1280}
        height={720}
        schema={thumbnailSchema}
        defaultProps={{
          phrase: "The Truth Revealed",
          style: "documentary",
          niche: "history",
        }}
      />
    </>
  );
};
