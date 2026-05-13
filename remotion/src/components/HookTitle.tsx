import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

// Words that should pop in the accent color — proper nouns, action verbs, stakes
const ACCENT_REGEX = /^(pakistan|india|china|russia|ukraine|israel|hamas|iran|iraq|war|attack|crisis|killed|destroyed|exposed|secret|hidden|truth|happened|backfired)$/i;

interface Props {
  title: string;
  /** Visible duration in frames (default ≈ 4s at 30fps). */
  durationFrames?: number;
}

export const HookTitle: React.FC<Props> = ({ title, durationFrames = 110 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(
    frame,
    [0, 6, durationFrames - 15, durationFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  if (opacity <= 0) return null;

  // Slight zoom on the hook as it's spoken
  const zoom = interpolate(frame, [0, durationFrames], [0.95, 1.06], {
    extrapolateRight: "clamp",
  });

  const words = title.split(/\s+/);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 60px",
        opacity,
        transform: `scale(${zoom})`,
      }}
    >
      <div
        style={{
          fontFamily,
          fontSize: 132,
          fontWeight: 900,
          textAlign: "center",
          textTransform: "uppercase",
          letterSpacing: "-0.04em",
          lineHeight: 0.95,
        }}
      >
        {words.map((word, i) => {
          const wordSpring = spring({
            frame: frame - i * 3,
            fps,
            config: { damping: 11, stiffness: 130, mass: 0.6 },
            durationInFrames: 25,
          });
          const clean = word.replace(/[^\w]/g, "");
          const isAccent = ACCENT_REGEX.test(clean);
          const lift = (1 - wordSpring) * 40;
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                margin: "0 0.18em",
                transform: `translateY(${lift}px) scale(${wordSpring})`,
                color: isAccent ? "#ffd93d" : "white",
                textShadow: isAccent
                  ? "0 0 40px rgba(255,217,61,0.55), 0 8px 24px rgba(0,0,0,0.85)"
                  : "0 8px 24px rgba(0,0,0,0.85)",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>
    </div>
  );
};
