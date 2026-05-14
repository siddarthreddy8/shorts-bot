import { useState } from 'react'
import { previewUrl } from '../lib/api'
import { useVideoStatus } from '../hooks/useVideoStatus'
import type { Video } from '../lib/types'
import { ScriptReview } from './ScriptReview'
import { StatusBadge } from './StatusBadge'
import { StepTracker } from './StepTracker'

function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso + 'Z').getTime()) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

export function VideoCard({ video, onRefresh }: { video: Video; onRefresh: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const liveStatus = useVideoStatus(video.video_id, video.status)

  const effectiveStatus = liveStatus?.status ?? video.status
  const canExpand  = video.status === 'script_drafted'
  const isRunning  = video.status === 'script_approved'
  const isDone     = video.status === 'uploaded'
  const hasPreview = video.status === 'video_rendered' || video.status === 'uploaded'

  const steps = liveStatus?.steps ?? (
    (isRunning || isDone || video.status === 'failed' || video.status === 'video_rendered')
      ? [
          { name: 'Storyboard', state: 'pending' as const, error: null },
          { name: 'Render',     state: 'pending' as const, error: null },
          { name: 'Upload',     state: 'pending' as const, error: null },
        ]
      : null
  )

  return (
    <div
      onClick={canExpand ? () => setExpanded((v) => !v) : undefined}
      style={{
        background: 'var(--c-card)',
        border: `1px solid ${expanded ? 'var(--c-gold)' : 'var(--c-border)'}`,
        borderRadius: 6,
        padding: '16px 20px',
        cursor: canExpand ? 'pointer' : 'default',
        transition: 'border-color 0.15s, box-shadow 0.15s',
        boxShadow: expanded ? '0 0 20px rgba(255,217,61,0.06)' : 'none',
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            margin: 0,
            fontSize: '0.95rem',
            fontWeight: 500,
            color: 'var(--c-text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {video.source_title ?? video.video_id}
          </p>
          <p style={{
            margin: '4px 0 0',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.68rem',
            color: 'var(--c-muted)',
          }}>
            {video.source_channel_name ?? '—'} · {timeAgo(video.updated_at)}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <StatusBadge status={effectiveStatus} />
          {canExpand && (
            <span style={{ color: 'var(--c-muted)', fontSize: '0.75rem', lineHeight: 1 }}>
              {expanded ? '▲' : '▼'}
            </span>
          )}
        </div>
      </div>

      {/* Step tracker */}
      {steps && <StepTracker steps={steps} />}

      {/* YouTube link */}
      {isDone && video.youtube_url && (
        <a
          href={video.youtube_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          style={{
            display: 'block',
            marginTop: 10,
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: 'var(--c-gold)',
            textDecoration: 'none',
          }}
        >
          ↗ {video.youtube_url}
        </a>
      )}

      {/* Inline video preview */}
      {hasPreview && (
        <video
          src={previewUrl(video.video_id)}
          controls
          onClick={(e) => e.stopPropagation()}
          style={{
            marginTop: 14,
            width: '100%',
            maxHeight: 280,
            borderRadius: 4,
            background: '#000',
            display: 'block',
          }}
        />
      )}

      {/* Inline script review */}
      {expanded && canExpand && (
        <div onClick={(e) => e.stopPropagation()}>
          <ScriptReview
            videoId={video.video_id}
            onApproved={() => {
              setExpanded(false)
              onRefresh()
            }}
          />
        </div>
      )}
    </div>
  )
}
