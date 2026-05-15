import type { Step } from '../lib/types'

function pillStyle(state: Step['state']): React.CSSProperties {
  const base: React.CSSProperties = {
    fontFamily: 'var(--font-mono)',
    fontSize: '0.6rem',
    fontWeight: 500,
    letterSpacing: '0.05em',
    padding: '3px 11px',
    borderRadius: 20,
    border: '1px solid transparent',
    whiteSpace: 'nowrap',
    transition: 'all 0.2s',
  }
  if (state === 'done') return { ...base, background: 'var(--c-gold-bg)', color: 'var(--c-gold-text)', border: '1px solid var(--c-gold-border)' }
  if (state === 'running') return { ...base, background: 'var(--c-blue-bg)', color: 'var(--c-blue)', border: '1px solid var(--c-blue-border)', animation: 'step-pulse 1.4s ease-in-out infinite' }
  if (state === 'failed') return { ...base, background: 'var(--c-red-bg)', color: 'var(--c-red)', border: '1px solid var(--c-red-border)' }
  return { ...base, color: 'var(--c-muted)' }
}

export function StepTracker({ steps }: { steps: Step[] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', marginTop: 10, flexWrap: 'wrap', gap: '2px 0' }}>
      {steps.map((step, i) => (
        <div key={step.name} style={{ display: 'flex', alignItems: 'center' }}>
          <span style={pillStyle(step.state)}>
            {step.state === 'done' ? '✓ ' : ''}{step.name}
          </span>
          {i < steps.length - 1 && (
            <span style={{ color: 'var(--c-muted2)', padding: '0 3px', fontSize: '0.65rem' }}>→</span>
          )}
        </div>
      ))}
    </div>
  )
}
