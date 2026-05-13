import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { Caption } from "../types";

const { fontFamily } = loadFont();

interface Props {
  captions: Caption[];
  /** Frame at which captions become visible (typically after the hook). */
  startFrame?: number;
  /** How many words to show centered on the current word. */
  windowSize?: number;
}

export const Captions: React.FC<Props> = ({
  captions,
  startFrame = 115,
  windowSize = 5,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (frame < startFrame || captions.length === 0) return null;

  const currentMs = (frame / fps) * 1000;

  // Find currently-spoken word
  let currentIdx = captions.findIndex(
    (c) => currentMs >= c.startMs && currentMs <= c.endMs + 200,
  );
  if (currentIdx === -1) {
    // Else: find next upcoming word
    currentIdx = captions.findIndex((c) => currentMs < c.startMs);
    if (currentIdx === -1) currentIdx = captions.length - 1;
  }

  const half = Math.floor(windowSize / 2);
  const windowStart = Math.max(0, currentIdx - half);
  const visible = captions.slice(windowStart, windowStart + windowSize);

  // Subtle entrance animation when a new word becomes active
  const activeCap = captions[currentIdx];
  const wordOpenedAt = activeCap ? (activeCap.startMs / 1000) * fps : 0;
  const pop = spring({
    frame: frame - wordOpenedAt,
    fps,
    config: { damping: 14, stiffness: 220, mass: 0.4 },
    durationInFrames: 12,
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 280,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 60px",
      }}
    >
      <div
        style={{
          fontFamily,
          fontSize: 76,
          fontWeight: 900,
          textAlign: "center",
          textTransform: "uppercase",
          letterSpacing: "-0.02em",
          lineHeight: 1.05,
          maxWidth: "100%",
        }}
      >
        {visible.map((cap, i) => {
          const wordIdx = windowStart + i;
          const isCurrent = wordIdx === currentIdx;
          const distance = Math.abs(wordIdx - currentIdx);

          let scale = 0.78;
          let color = "rgba(255,255,255,0.35)";
          let glow = "0 4px 16px rgba(0,0,0,0.85)";

          if (isCurrent) {
            scale = 1.18 * (0.92 + pop * 0.08);
            color = "#ffd93d";
            glow =
              "0 0 26px rgba(255,217,61,0.55), 0 4px 20px rgba(0,0,0,0.9)";
          } else if (distance === 1) {
            scale = 0.95;
            color = "white";
          } else if (distance === 2) {
            scale = 0.82;
            color = "rgba(255,255,255,0.55)";
          }

          return (
            <span
              key={wordIdx}
              style={{
                display: "inline-block",
                margin: "0 0.18em",
                transform: `scale(${scale})`,
                color,
                textShadow: glow,
              }}
            >
              {cap.word}
            </span>
          );
        })}
      </div>
    </div>
  );
};
