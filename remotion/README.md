# Remotion Subproject — Hoog-style Templates

Programmatic video templates for the Shorts-Bot pipeline. Python orchestration shells out to `@remotion/cli` to render approved scripts into MP4s.

## Templates

| ID | Use case |
|---|---|
| `HoogMap` | Animated globe/map zoom + bold title overlay. Hoog signature for geo/world-news topics. |
| `HoogTypography` | Pure-typography card on parallax grid. Use for stat-heavy / claim-driven scripts. |

## Develop

```bash
cd remotion
npm install
npm run dev          # Remotion Studio — preview compositions in browser
```

## Render (programmatic, called from Python)

```bash
npm run render -- HoogMap out.mp4 --props='{"title":"...","captions":[...],"audioSrc":"voiceover.mp3"}'
```

Output goes to `out/` (gitignored).

## Adding a new template

1. Create `src/compositions/<Name>.tsx` exporting both a component and a `z.object(...)` schema
2. Register it in `src/Root.tsx`
3. Map Python topic → template ID in `src/video/template_picker.py`
