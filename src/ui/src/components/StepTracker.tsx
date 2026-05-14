import type { Step } from '../lib/types'

export function StepTracker({ steps }: { steps: Step[] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', marginTop: 12 }}>
      {steps.map((step, i) => (
        <div key={step.name} style={{ display: 'flex', alignItems: 'center' }}>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              fontWeight: 500,
              letterSpacing: '0.06em',
              padding: '3px 12px',
              borderRadius: 20,
              background:
                step.state === 'done'    ? 'var(--c-gold)' :
                step.state === 'failed'  ? 'var(--c-red)'  : 'transparent',
              color:
                step.state === 'done'    ? '#000' :
                step.state === 'running' ? 'var(--c-gold)' :
                step.state === 'failed'  ? '#fff' : 'var(--c-muted)',
              border:
                step.state === 'running' ? '1px solid var(--c-gold)' :
                step.state === 'failed'  ? '1px solid var(--c-red)'  : '1px solid transparent',
              animation: step.state === 'running' ? 'pulse 1.5s ease-in-out infinite' : 'none',
            }}
          >
            {step.state === 'done' ? '✓ ' : ''}{step.name}
          </span>
          {i < steps.length - 1 && (
            <span style={{ color: 'var(--c-muted)', padding: '0 4px', fontSize: '0.7rem' }}>→</span>
          )}
        </div>
      ))}
    </div>
  )
}
