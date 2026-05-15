import type { PipelineStatus } from '../lib/types'

interface BadgeConfig {
  label: string
  color: string
  bg: string
  border: string
}

const CONFIG: Record<string, BadgeConfig> = {
  discovered:      { label: 'DISCOVERED',       color: 'var(--c-muted)',   bg: 'var(--c-surface)',    border: 'var(--c-border)' },
  transcribed:     { label: 'TRANSCRIBED',       color: 'var(--c-blue)',    bg: 'var(--c-blue-bg)',   border: 'var(--c-blue-border)' },
  script_drafted:  { label: 'NEEDS REVIEW',      color: 'var(--c-gold-text)', bg: 'var(--c-gold-bg)', border: 'var(--c-gold-border)' },
  script_approved: { label: 'RUNNING',           color: 'var(--c-blue)',    bg: 'var(--c-blue-bg)',   border: 'var(--c-blue-border)' },
  video_rendered:  { label: 'READY TO PUBLISH',  color: 'var(--c-purple)',  bg: 'var(--c-purple-bg)', border: 'var(--c-purple-border)' },
  uploaded:        { label: 'UPLOADED',          color: 'var(--c-green)',   bg: 'var(--c-green-bg)',  border: 'var(--c-green-border)' },
  failed:          { label: 'FAILED',            color: 'var(--c-red)',     bg: 'var(--c-red-bg)',    border: 'var(--c-red-border)' },
  skipped:         { label: 'SKIPPED',           color: 'var(--c-muted)',   bg: 'var(--c-surface)',   border: 'var(--c-border)' },
}

export function StatusBadge({ status }: { status: PipelineStatus }) {
  const cfg = CONFIG[status] ?? { label: status.toUpperCase(), color: 'var(--c-muted)', bg: 'var(--c-surface)', border: 'var(--c-border)' }
  return (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontSize: '0.62rem',
      fontWeight: 500,
      letterSpacing: '0.08em',
      color: cfg.color,
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
      borderRadius: 3,
      padding: '3px 8px',
      whiteSpace: 'nowrap',
    }}>
      {cfg.label}
    </span>
  )
}
