import {
  AbsoluteFill,
  Video,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

interface Props {
  src: string;
  durationInFrames: number;
}

const FADE = 10;

export const SceneVideo: React.FC<Props> = ({ src, durationInFrames }) => {
  const frame = useCurrentFrame();

  const fadeIn = interpolate(frame, [0, FADE], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - FADE, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp" },
  );
  const opacity = Math.min(fadeIn, fadeOut);

  return (
    <AbsoluteFill style={{ opacity, background: "#000" }}>
      <Video
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
        }}
      />
    </AbsoluteFill>
  );
};
