import { VideoQueue } from './components/VideoQueue'

export function App() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--c-bg)' }}>
      <header style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        background: 'rgba(8,12,24,0.92)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--c-border)',
        padding: '0 32px',
        height: 52,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontWeight: 500,
          fontSize: '0.85rem',
          letterSpacing: '0.18em',
          color: 'var(--c-gold)',
        }}>
          SHORTS BOT
        </span>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.65rem',
          color: 'var(--c-muted)',
          letterSpacing: '0.06em',
        }}>
          PIPELINE DASHBOARD
        </span>
      </header>
      <main style={{ maxWidth: 860, margin: '0 auto', padding: '36px 24px' }}>
        <VideoQueue />
      </main>
    </div>
  )
}
