import {
  AbsoluteFill,
  Audio,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";
import { loadFont } from "@remotion/google-fonts/Inter";
import { Captions } from "../components/Captions";
import { captionSchema } from "../types";

const { fontFamily } = loadFont();

export const hoogMapSchema = z.object({
  title: z.string(),
  captions: z.array(captionSchema),
  audioSrc: z.string().nullable(),
  focusRegion: z.enum(["world", "europe", "asia", "india", "americas"]),
});

type Props = z.infer<typeof hoogMapSchema>;

// Hoog-signature: slow zoom into an animated globe/map with title overlay.
export const HoogMap: React.FC<Props> = ({ title, captions, audioSrc }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Slow zoom on the map — Hoog camera move
  const zoom = interpolate(frame, [0, durationInFrames], [1.0, 1.25], {
    extrapolateRight: "clamp",
  });

  // Title fades in over 30 frames, holds, fades out
  const titleOpacity = interpolate(
    frame,
    [0, 18, 90, 110],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const titleY = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 90 },
    durationInFrames: 30,
  });

  return (
    <AbsoluteFill style={{ background: "#0a0e1a" }}>
      {/* Background gradient — atmospheric */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(40,80,140,0.4) 0%, rgba(10,14,26,1) 70%)",
        }}
      />

      {/* Map placeholder — Sprint 3 will replace with react-simple-maps */}
      <AbsoluteFill
        style={{
          transform: `scale(${zoom})`,
          transformOrigin: "center",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <div
          style={{
            width: 1400,
            height: 1400,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(60,120,200,0.3) 0%, rgba(20,40,80,0.6) 60%, transparent 100%)",
            border: "2px solid rgba(120,180,255,0.2)",
            boxShadow: "inset 0 0 200px rgba(80,150,220,0.25)",
          }}
        />
      </AbsoluteFill>

      {/* Title overlay */}
      <AbsoluteFill
        style={{
          justifyContent: "flex-start",
          alignItems: "center",
          paddingTop: 220,
          opacity: titleOpacity,
          transform: `translateY(${(1 - titleY) * 30}px)`,
        }}
      >
        <div
          style={{
            fontFamily,
            fontSize: 96,
            fontWeight: 900,
            color: "white",
            textAlign: "center",
            letterSpacing: "-0.03em",
            lineHeight: 1.0,
            padding: "0 60px",
            textTransform: "uppercase",
            textShadow: "0 8px 40px rgba(0,0,0,0.8)",
          }}
        >
          {title}
        </div>
      </AbsoluteFill>

      <Captions captions={captions} />

      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}
    </AbsoluteFill>
  );
};
