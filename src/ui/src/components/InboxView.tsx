import type { Video } from '../lib/types'
import { InboxCard } from './InboxCard'

export function InboxView({ videos, onRefresh }: { videos: Video[]; onRefresh: () => void }) {
  const inboxVideos = videos
    .filter((v) => v.status === 'transcribed' || v.status === 'script_drafted')
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))

  const awaitingCount = inboxVideos.filter((v) => v.status === 'transcribed').length

  return (
    <div>
      {/* Section header */}
      <div style={{
        padding: '14px 20px 12px',
        borderBottom: '1px solid var(--c-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: 'var(--c-bg)',
        position: 'sticky',
        top: 0,
        zIndex: 1,
      }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.68rem',
          fontWeight: 600,
          color: awaitingCount > 0 ? 'var(--c-blue)' : 'var(--c-muted)',
          letterSpacing: '0.1em',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          {awaitingCount > 0 && (
            <span style={{
              display: 'inline-block',
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: 'var(--c-blue)',
              animation: 'pulse-dot 2s ease-in-out infinite',
              flexShrink: 0,
            }} />
          )}
          {awaitingCount > 0
            ? `◎ INBOX — ${awaitingCount} AWAITING SCRIPT`
            : '◎ INBOX'}
        </div>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.58rem',
          color: 'var(--c-muted)',
          letterSpacing: '0.06em',
        }}>
          {inboxVideos.length} TOTAL
        </span>
      </div>

      {/* Cards */}
      <div style={{
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 7,
      }}>
        {inboxVideos.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 40, paddingBottom: 24 }}>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--c-muted)', margin: '0 0 6px' }}>
              No videos awaiting review.
            </p>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.62rem', color: 'var(--c-muted2)', margin: 0 }}>
              Poll channels or add a URL to get started.
            </p>
          </div>
        )}

        {inboxVideos.map((v) => (
          <InboxCard key={v.video_id} video={v} onRefresh={onRefresh} />
        ))}
      </div>
    </div>
  )
}
