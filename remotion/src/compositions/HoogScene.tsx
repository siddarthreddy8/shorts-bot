import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
} from "remotion";
import { z } from "zod";

import { Captions } from "../components/Captions";
import { HookTitle } from "../components/HookTitle";
import { ParticleField } from "../components/ParticleField";
import { SceneImage } from "../components/SceneImage";
import { captionSchema } from "../types";

const FPS = 30;
const HOOK_FRAMES = 110;

export const sceneSchema = z.object({
  start_ms: z.number(),
  end_ms: z.number(),
  prompt: z.string(),
  motion: z.enum(["zoom_in", "zoom_out", "pan_left", "pan_right", "static"]),
  image_path: z.string(),
});

export const hoogSceneSchema = z.object({
  title: z.string(),
  captions: z.array(captionSchema),
  scenes: z.array(sceneSchema),
  audioSrc: z.string().nullable(),
});

type Props = z.infer<typeof hoogSceneSchema>;

export const HoogScene: React.FC<Props> = ({ title, captions, scenes, audioSrc }) => {
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {/* B-roll scenes with motion + crossfade */}
      {scenes.map((scene, i) => {
        const startFrame = Math.max(0, Math.round((scene.start_ms / 1000) * FPS));
        const endFrame = Math.round((scene.end_ms / 1000) * FPS);
        const dur = Math.max(1, endFrame - startFrame);
        // Overlap neighbouring scenes by FADE frames for true crossfade
        const fromFrame = Math.max(0, startFrame - (i === 0 ? 0 : 5));
        const durWithOverlap = dur + (i === 0 ? 0 : 5) + (i === scenes.length - 1 ? 0 : 5);
        return (
          <Sequence
            key={i}
            from={fromFrame}
            durationInFrames={durWithOverlap}
          >
            <SceneImage
              src={scene.image_path}
              motion={scene.motion}
              durationInFrames={durWithOverlap}
            />
          </Sequence>
        );
      })}

      {/* Dark gradient — top + bottom for hook + caption legibility */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, transparent 22%, transparent 58%, rgba(0,0,0,0.75) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* Soft vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,0.55) 100%)",
          pointerEvents: "none",
        }}
      />

      {/* Subtle particles — reduce count to not fight the imagery */}
      <ParticleField />

      {/* Hook title overlay (first ~3.7s) */}
      <HookTitle title={title} durationFrames={HOOK_FRAMES} />

      {/* Captions (after hook fades) */}
      <Captions captions={captions} startFrame={HOOK_FRAMES + 5} />

      {audioSrc ? <Audio src={staticFile(audioSrc)} /> : null}
    </AbsoluteFill>
  );
};
