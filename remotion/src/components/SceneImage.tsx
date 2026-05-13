import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

export type MotionType = "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "static";

interface Props {
  src: string;
  motion: MotionType;
  durationInFrames: number;
}

const FADE = 10;  // frames for crossfade in/out

export const SceneImage: React.FC<Props> = ({ src, motion, durationInFrames }) => {
  const frame = useCurrentFrame();

  // Per-scene motion
  let scale = 1.0;
  let translateX = 0;

  switch (motion) {
    case "zoom_in":
      scale = interpolate(frame, [0, durationInFrames], [1.0, 1.18]);
      break;
    case "zoom_out":
      scale = interpolate(frame, [0, durationInFrames], [1.18, 1.0]);
      break;
    case "pan_left":
      scale = 1.12;
      translateX = interpolate(frame, [0, durationInFrames], [80, -80]);
      break;
    case "pan_right":
      scale = 1.12;
      translateX = interpolate(frame, [0, durationInFrames], [-80, 80]);
      break;
    case "static":
      scale = 1.03;
      break;
  }

  // Crossfade in/out — keeps scene transitions smooth
  const fadeIn = interpolate(frame, [0, FADE], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - FADE, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp" },
  );
  const opacity = Math.min(fadeIn, fadeOut);

  return (
    <AbsoluteFill style={{ opacity, background: "#000" }}>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${translateX}px, 0)`,
          transformOrigin: "50% 50%",
        }}
      />
    </AbsoluteFill>
  );
};
