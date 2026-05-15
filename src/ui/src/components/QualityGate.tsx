import { useState } from 'react'
import { publishVideo, rejectRender } from '../lib/api'

export function QualityGate({ videoId, onRefresh }: { videoId: string; onRefresh: () => void }) {
  const [loading, setLoading] = useState<'publish' | 'reject' | null>(null)

  const handlePublish = async () => {
    setLoading('publish')
    try { await publishVideo(videoId); onRefresh() } catch { setLoading(null) }
  }

  const handleReject = async () => {
    setLoading('reject')
    try { await rejectRender(videoId); onRefresh() } catch { setLoading(null) }
  }

  return (
    <div style={{
      marginTop: 12,
      padding: '10px 13px',
      background: 'var(--c-purple-bg)',
      border: '1px solid var(--c-purple-border)',
      borderRadius: 6,
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      flexWrap: 'wrap',
    }}>
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '0.63rem',
        color: 'var(--c-purple)',
        flex: 1,
        minWidth: 120,
      }}>
        Preview the render above, then publish or reject
      </span>
      <button
        onClick={handleReject}
        disabled={loading !== null}
        style={{
          background: 'var(--c-red-bg)',
          border: '1px solid var(--c-red-border)',
          color: 'var(--c-red)',
          padding: '7px 14px',
          borderRadius: 4,
          fontFamily: 'var(--font-mono)',
          fontSize: '0.62rem',
          fontWeight: 500,
          cursor: loading !== null ? 'not-allowed' : 'pointer',
          opacity: loading === 'reject' ? 0.6 : 1,
          minHeight: 36,
        }}
      >
        {loading === 'reject' ? '…' : '✕ Reject'}
      </button>
      <button
        onClick={handlePublish}
        disabled={loading !== null}
        style={{
          background: 'var(--c-green)',
          border: 'none',
          color: '#fff',
          padding: '7px 16px',
          borderRadius: 4,
          fontFamily: 'var(--font-mono)',
          fontSize: '0.62rem',
          fontWeight: 600,
          cursor: loading !== null ? 'not-allowed' : 'pointer',
          opacity: loading === 'publish' ? 0.6 : 1,
          minHeight: 36,
          boxShadow: '0 1px 4px rgba(22,163,74,0.3)',
        }}
      >
        {loading === 'publish' ? 'Publishing…' : '↑ Publish to YouTube'}
      </button>
    </div>
  )
}
