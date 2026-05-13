import {
  AbsoluteFill,
  Audio,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";
import { Captions } from "../components/Captions";
import { HookTitle } from "../components/HookTitle";
import { ParticleField } from "../components/ParticleField";
import { captionSchema } from "../types";

export const hoogTypographySchema = z.object({
  title: z.string(),
  captions: z.array(captionSchema),
  audioSrc: z.string().nullable(),
});

type Props = z.infer<typeof hoogTypographySchema>;

const HOOK_FRAMES = 110;  // hook visible for ~3.7s

export const HoogTypography: React.FC<Props> = ({ title, captions, audioSrc }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Slow Ken Burns zoom across the whole scene
  const sceneZoom = interpolate(frame, [0, durationInFrames], [1.0, 1.07], {
    extrapolateRight: "clamp",
  });

  // Background grid parallax — different speeds for depth
  const gridShiftA = interpolate(frame, [0, durationInFrames], [0, 280]);
  const gridShiftB = interpolate(frame, [0, durationInFrames], [0, 140]);

  // Subtle ambient pulse — radial glow breathes
  const pulse = (Math.sin(frame * 0.025) + 1) / 2;          // 0..1
  const glowOpacity = 0.18 + pulse * 0.12;

  // Color tint — shifts from cool blue → slight purple over time
  const hueShift = interpolate(frame, [0, durationInFrames], [0, 18]);

  return (
    <AbsoluteFill style={{ background: "#080c18", filter: `hue-rotate(${hueShift}deg)` }}>
      {/* Ken Burns wrapper — everything inside zooms together */}
      <AbsoluteFill style={{ transform: `scale(${sceneZoom})`, transformOrigin: "50% 50%" }}>
        {/* Far parallax grid — small + dim */}
        <AbsoluteFill
          style={{
            backgroundImage: `
              linear-gradient(rgba(80,140,210,0.05) 1px, transparent 1px),
              linear-gradient(90deg, rgba(80,140,210,0.05) 1px, transparent 1px)
            `,
            backgroundSize: "60px 60px",
            transform: `translate(${-gridShiftB}px, ${-gridShiftB / 1.5}px)`,
          }}
        />
        {/* Near parallax grid — bigger + brighter */}
        <AbsoluteFill
          style={{
            backgroundImage: `
              linear-gradient(rgba(100,170,240,0.10) 1px, transparent 1px),
              linear-gradient(90deg, rgba(100,170,240,0.10) 1px, transparent 1px)
            `,
            backgroundSize: "140px 140px",
            transform: `translate(${-gridShiftA}px, ${-gridShiftA / 2}px)`,
          }}
        />

        {/* Atmospheric radial glow */}
        <AbsoluteFill
          style={{
            background: `radial-gradient(ellipse at 50% 42%, rgba(80,150,230,${glowOpacity}) 0%, transparent 65%)`,
          }}
        />

        {/* Floating particles */}
        <ParticleField />

        {/* Soft horizon line for depth */}
        <AbsoluteFill
          style={{
            background:
              "linear-gradient(to bottom, transparent 60%, rgba(60,100,160,0.20) 75%, transparent 90%)",
          }}
        />

        {/* Vignette */}
        <AbsoluteFill
          style={{
            background:
              "radial-gradient(ellipse at center, transparent 38%, rgba(0,0,0,0.75) 100%)",
            pointerEvents: "none",
          }}
        />
      </AbsoluteFill>

      {/* Foreground: hook title (fades out after ~3.7s) */}
      <HookTitle title={title} durationFrames={HOOK_FRAMES} />

      {/* Foreground: dynamic captions (active after the hook) */}
      <Captions captions={captions} startFrame={HOOK_FRAMES + 5} />

      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}
    </AbsoluteFill>
  );
};
