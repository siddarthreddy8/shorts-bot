import { useState } from 'react'
import { dismissVideo, previewUrl, retryVideo } from '../lib/api'
import { useVideoStatus } from '../hooks/useVideoStatus'
import type { Video } from '../lib/types'
import { QualityGate } from './QualityGate'
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
  const canExpand   = effectiveStatus === 'script_drafted'
  const showSteps   = ['script_approved', 'video_rendered', 'uploaded', 'failed'].includes(effectiveStatus)
  const isDone      = effectiveStatus === 'uploaded'
  const isRendered  = effectiveStatus === 'video_rendered'
  const isFailed    = effectiveStatus === 'failed'
  const hasMp4      = isRendered || isDone
  const [recovering, setRecovering] = useState<'retry' | 'dismiss' | null>(null)

  const steps = liveStatus?.steps ?? (
    showSteps ? [
      { name: 'Storyboard', state: 'pending' as const, error: null },
      { name: 'Render',     state: 'pending' as const, error: null },
      { name: 'Upload',     state: 'pending' as const, error: null },
    ] : null
  )

  const cardStyle: React.CSSProperties = {
    background: 'var(--c-card)',
    border: `1.5px solid ${expanded ? 'var(--c-gold)' : 'var(--c-border)'}`,
    borderRadius: 8,
    padding: '13px 16px',
    cursor: canExpand ? 'pointer' : 'default',
    boxShadow: expanded
      ? '0 0 0 3px var(--c-gold-bg), 0 2px 12px rgba(0,0,0,0.06)'
      : '0 1px 4px rgba(0,0,0,0.04)',
    transition: 'border-color 0.18s, box-shadow 0.18s, transform 0.12s',
  }

  return (
    <div
      onClick={canExpand ? () => setExpanded((v) => !v) : undefined}
      style={cardStyle}
      onMouseEnter={(e) => { if (!expanded) (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)' }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = '' }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            margin: 0,
            fontSize: '0.88rem',
            fontWeight: 500,
            color: 'var(--c-text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            letterSpacing: '-0.01em',
            lineHeight: 1.4,
          }}>
            {video.source_title ?? video.video_id}
          </p>
          <p style={{
            margin: '3px 0 0',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.62rem',
            color: 'var(--c-muted)',
          }}>
            {video.source_channel_name ?? '—'} · {timeAgo(video.updated_at)}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          <StatusBadge status={effectiveStatus} />
          {canExpand && (
            <span style={{
              color: expanded ? 'var(--c-gold)' : 'var(--c-muted)',
              fontSize: '0.65rem',
              lineHeight: 1,
              transition: 'color 0.15s',
            }}>
              {expanded ? '▲' : '▼'}
            </span>
          )}
        </div>
      </div>

      {/* Step tracker */}
      {steps && <StepTracker steps={steps} />}

      {/* Failed video recovery */}
      {isFailed && (
        <div style={{ marginTop: 10 }}>
          {video.failure_reason && (
            <p style={{
              margin: '0 0 8px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--c-red)',
              background: 'var(--c-red-bg)',
              border: '1px solid var(--c-red-border)',
              borderRadius: 4,
              padding: '5px 9px',
              wordBreak: 'break-word',
            }}>
              {video.failure_reason}
            </p>
          )}
          <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', gap: 6 }}>
            <button
              disabled={recovering !== null}
              onClick={async () => {
                setRecovering('retry')
                try { await retryVideo(video.video_id); onRefresh() } catch { setRecovering(null) }
              }}
              style={{
                flex: 1,
                height: 36,
                background: recovering === 'retry' ? 'var(--c-border)' : 'var(--c-gold)',
                border: 'none',
                borderRadius: 4,
                color: recovering === 'retry' ? 'var(--c-muted)' : '#fff',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.62rem',
                fontWeight: 600,
                letterSpacing: '0.08em',
                cursor: recovering ? 'not-allowed' : 'pointer',
              }}
            >
              {recovering === 'retry' ? '↺ RETRYING…' : '↺ RETRY'}
            </button>
            <button
              disabled={recovering !== null}
              onClick={async () => {
                setRecovering('dismiss')
                try { await dismissVideo(video.video_id); onRefresh() } catch { setRecovering(null) }
              }}
              style={{
                height: 36,
                padding: '0 12px',
                background: 'var(--c-surface)',
                border: '1px solid var(--c-border)',
                borderRadius: 4,
                color: 'var(--c-muted)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.62rem',
                cursor: recovering ? 'not-allowed' : 'pointer',
              }}
            >
              ✕ Dismiss
            </button>
          </div>
        </div>
      )}

      {/* Inline video preview */}
      {hasMp4 && (
        <video
          src={previewUrl(video.video_id)}
          controls
          onClick={(e) => e.stopPropagation()}
          style={{
            marginTop: 12,
            width: '100%',
            maxHeight: 280,
            borderRadius: 5,
            background: '#000',
            display: 'block',
          }}
        />
      )}

      {/* Quality gate for video_rendered */}
      {isRendered && (
        <div onClick={(e) => e.stopPropagation()}>
          <QualityGate videoId={video.video_id} onRefresh={onRefresh} />
        </div>
      )}

      {/* YouTube link for uploaded */}
      {isDone && video.youtube_url && (
        <a
          href={video.youtube_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            marginTop: 9,
            fontFamily: 'var(--font-mono)',
            fontSize: '0.62rem',
            color: 'var(--c-blue)',
            textDecoration: 'none',
          }}
        >
          ↗ {video.youtube_url}
        </a>
      )}

      {/* Script review expansion */}
      {expanded && canExpand && (
        <div onClick={(e) => e.stopPropagation()}>
          <ScriptReview
            videoId={video.video_id}
            onApproved={() => { setExpanded(false); onRefresh() }}
            onRefresh={() => { setExpanded(false); onRefresh() }}
          />
        </div>
      )}
    </div>
  )
}
