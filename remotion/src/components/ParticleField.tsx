import { useCurrentFrame, useVideoConfig } from "remotion";

// Deterministic pseudo-random — same particle positions across all render workers.
const seedRand = (seed: number) => {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
};

const N = 70;
const PARTICLES = Array.from({ length: N }, (_, i) => ({
  id: i,
  x:        seedRand(i * 1.7) * 100,
  y:        seedRand(i * 2.3 + 11) * 100,
  size:     2 + seedRand(i * 3.1 + 22) * 5,
  speed:    0.03 + seedRand(i * 4.2 + 33) * 0.12,
  opacity:  0.15 + seedRand(i * 5.4 + 44) * 0.40,
  phaseX:   seedRand(i * 6.7 + 55) * Math.PI * 2,
  drift:    seedRand(i * 7.9 + 66) * 25 + 10,
  hueShift: seedRand(i * 8.3 + 77),
}));

export const ParticleField: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      {PARTICLES.map((p) => {
        const offsetX = Math.sin(t * p.speed * 2 + p.phaseX) * p.drift;
        const offsetY = -(t * p.speed * 18) % 140;          // slow upward drift, wraps
        const hue = 200 + p.hueShift * 40;                  // blue→cyan range
        const top = (((p.y + offsetY) % 100) + 100) % 100;
        return (
          <div
            key={p.id}
            style={{
              position: "absolute",
              left: `${p.x}%`,
              top: `${top}%`,
              transform: `translate(${offsetX}px, 0)`,
              width: p.size,
              height: p.size,
              borderRadius: "50%",
              background: `hsla(${hue}, 80%, 70%, ${p.opacity})`,
              boxShadow: `0 0 ${p.size * 5}px hsla(${hue}, 80%, 65%, ${p.opacity * 0.6})`,
            }}
          />
        );
      })}
    </div>
  );
};
