import { AbsoluteFill } from "remotion";
import { z } from "zod";

export const thumbnailSchema = z.object({
  phrase: z.string(),
  style: z.string(),
  niche: z.string(),
});

type Props = z.infer<typeof thumbnailSchema>;

const NICHE_PALETTE: Record<string, { bg: string; accent: string }> = {
  history:     { bg: "#0a0e1a", accent: "#c97a20" },
  crime:       { bg: "#0d0a0a", accent: "#c0392b" },
  tech:        { bg: "#080c18", accent: "#2980b9" },
  politics:    { bg: "#0a0c10", accent: "#8e44ad" },
  science:     { bg: "#080f14", accent: "#27ae60" },
  default:     { bg: "#080c18", accent: "#e67e22" },
};

function palette(niche: string) {
  return NICHE_PALETTE[niche.toLowerCase()] ?? NICHE_PALETTE.default;
}

export const Thumbnail: React.FC<Props> = ({ phrase, niche }) => {
  const { bg, accent } = palette(niche);

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 40% 50%, ${accent}33 0%, ${bg} 65%)`,
        backgroundColor: bg,
        fontFamily: "'Inter', 'Arial Black', sans-serif",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        padding: "60px 80px",
      }}
    >
      {/* Atmospheric grid */}
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(${accent}18 1px, transparent 1px),
            linear-gradient(90deg, ${accent}18 1px, transparent 1px)
          `,
          backgroundSize: "80px 80px",
          opacity: 0.4,
        }}
      />

      {/* Vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.80) 100%)",
        }}
      />

      {/* Accent bar */}
      <div
        style={{
          position: "absolute",
          left: 60,
          top: "50%",
          transform: "translateY(-50%)",
          width: 8,
          height: "40%",
          background: accent,
          borderRadius: 4,
          boxShadow: `0 0 24px ${accent}99`,
        }}
      />

      {/* Main phrase */}
      <p
        style={{
          position: "relative",
          zIndex: 10,
          color: "#ffffff",
          fontSize: 88,
          fontWeight: 900,
          lineHeight: 1.1,
          textAlign: "center",
          textTransform: "uppercase",
          letterSpacing: "-1px",
          textShadow: `0 4px 32px rgba(0,0,0,0.9), 0 0 60px ${accent}66`,
          margin: 0,
        }}
      >
        {phrase}
      </p>

      {/* Niche label */}
      <p
        style={{
          position: "absolute",
          bottom: 40,
          right: 60,
          color: `${accent}cc`,
          fontSize: 28,
          fontWeight: 600,
          letterSpacing: "3px",
          textTransform: "uppercase",
          margin: 0,
          zIndex: 10,
        }}
      >
        {niche.toUpperCase()}
      </p>
    </AbsoluteFill>
  );
};
