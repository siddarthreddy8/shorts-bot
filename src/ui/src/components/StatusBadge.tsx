import type { PipelineStatus } from '../lib/types'

const CONFIG: Record<string, { label: string; color: string }> = {
  discovered:      { label: 'DISCOVERED',   color: 'var(--c-dim)' },
  transcribed:     { label: 'TRANSCRIBED',  color: 'var(--c-dim)' },
  script_drafted:  { label: 'NEEDS REVIEW', color: 'var(--c-gold)' },
  script_approved: { label: 'RUNNING',      color: 'var(--c-blue)' },
  video_rendered:  { label: 'RENDERING',    color: 'var(--c-blue)' },
  uploaded:        { label: 'UPLOADED',     color: 'var(--c-green)' },
  failed:          { label: 'FAILED',       color: 'var(--c-red)' },
  skipped:         { label: 'SKIPPED',      color: 'var(--c-dim)' },
}

export function StatusBadge({ status }: { status: PipelineStatus }) {
  const { label, color } = CONFIG[status] ?? { label: status.toUpperCase(), color: 'var(--c-dim)' }
  return (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontSize: '0.65rem',
      fontWeight: 500,
      letterSpacing: '0.08em',
      color,
      border: `1px solid ${color}`,
      borderRadius: 2,
      padding: '2px 7px',
      whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  )
}
