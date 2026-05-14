import { useVideos } from '../hooks/useVideos'
import { VideoCard } from './VideoCard'

export function VideoQueue() {
  const { videos, loading, refresh } = useVideos()

  if (loading) {
    return (
      <p style={{ color: 'var(--c-muted)', fontFamily: 'var(--font-mono)', textAlign: 'center', marginTop: 80 }}>
        Loading queue…
      </p>
    )
  }

  if (videos.length === 0) {
    return (
      <p style={{ color: 'var(--c-muted)', fontFamily: 'var(--font-mono)', textAlign: 'center', marginTop: 80 }}>
        No videos in pipeline yet.
      </p>
    )
  }

  const pending = videos.filter((v) => v.status === 'script_drafted').length

  return (
    <div>
      {pending > 0 && (
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.7rem',
          color: 'var(--c-gold)',
          marginBottom: 20,
          letterSpacing: '0.08em',
        }}>
          ● {pending} VIDEO{pending !== 1 ? 'S' : ''} NEED{pending === 1 ? 'S' : ''} REVIEW
        </p>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {videos.map((v) => (
          <VideoCard key={v.video_id} video={v} onRefresh={refresh} />
        ))}
      </div>
    </div>
  )
}
