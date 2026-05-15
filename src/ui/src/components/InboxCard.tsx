import { useEffect, useRef, useState } from 'react'
import { fetchStatus, generateScript } from '../lib/api'
import type { Video } from '../lib/types'
import { ScriptReview } from './ScriptReview'
import { StatusBadge } from './StatusBadge'

const STYLES = ['Documentary', 'Comedy', 'Storytelling', 'Explainer', 'Serious', 'Sarcastic']

function describeError(err: unknown): string {
  const msg = err instanceof Error ? err.message : ''
  if (msg === 'SERVER_DOWN')      return 'API server is not running — start it on port 8000'
  if (msg.startsWith('HTTP_422')) return 'Invalid request — check language/style selection'
  if (msg.startsWith('HTTP_5'))   return 'Server error — check API terminal for details'
  return 'Failed to start generation'
}

function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso + 'Z').getTime()) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

export function InboxCard({ video, onRefresh }: { video: Video; onRefresh: () => void }) {
  const savedLang = video.target_language ?? 'english'
  const savedStyles: string[] = (() => {
    try { return JSON.parse(video.styles_json ?? '[]') } catch { return [] }
  })()

  const [language, setLanguage] = useState<'english' | 'hindi'>(
    savedLang === 'hindi' ? 'hindi' : 'english'
  )
  const [selectedStyles, setSelectedStyles] = useState<string[]>(
    savedStyles.length > 0 ? savedStyles : ['Documentary']
  )
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const isTranscribed = video.status === 'transcribed'
  const isDrafted = video.status === 'script_drafted'

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  function toggleStyle(style: string) {
    setSelectedStyles((prev) =>
      prev.includes(style) ? prev.filter((s) => s !== style) : [...prev, style]
    )
  }

  async function handleGenerate() {
    if (selectedStyles.length === 0) {
      setError('Select at least one style')
      return
    }
    setError(null)
    setGenerating(true)
    try {
      await generateScript(video.video_id, language, selectedStyles.map((s) => s.toLowerCase()))
    } catch (err) {
      setError(describeError(err))
      setGenerating(false)
      return
    }
    pollRef.current = setInterval(async () => {
      try {
        const status = await fetchStatus(video.video_id)
        if (status.status === 'script_drafted') {
          if (pollRef.current) clearInterval(pollRef.current)
          onRefresh()
        } else if (status.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current)
          setGenerating(false)
          setError('Script generation failed')
        }
      } catch { /* keep polling */ }
    }, 2000)
  }

  return (
    <div style={{
      background: 'var(--c-card)',
      border: `1.5px solid ${isDrafted ? 'var(--c-gold)' : 'var(--c-border)'}`,
      borderRadius: 8,
      padding: '13px 16px',
      boxShadow: isDrafted
        ? '0 0 0 3px var(--c-gold-bg), 0 2px 12px rgba(0,0,0,0.06)'
        : '0 1px 4px rgba(0,0,0,0.04)',
    }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, marginBottom: 12 }}>
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
        <StatusBadge status={video.status} />
      </div>

      {/* Transcribed state: language + styles + generate */}
      {isTranscribed && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Language toggle */}
          <div>
            <p style={{
              margin: '0 0 6px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--c-muted)',
              letterSpacing: '0.08em',
            }}>LANGUAGE</p>
            <div style={{ display: 'flex', gap: 6 }}>
              {(['english', 'hindi'] as const).map((lang) => (
                <button
                  key={lang}
                  onClick={() => setLanguage(lang)}
                  style={{
                    flex: 1,
                    height: 44,
                    border: `1.5px solid ${language === lang ? 'var(--c-gold)' : 'var(--c-border)'}`,
                    background: language === lang ? 'var(--c-gold-bg)' : 'var(--c-surface)',
                    color: language === lang ? 'var(--c-gold-text)' : 'var(--c-muted)',
                    borderRadius: 6,
                    cursor: 'pointer',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.68rem',
                    fontWeight: language === lang ? 700 : 400,
                    letterSpacing: '0.1em',
                    transition: 'all 0.15s',
                  }}
                >
                  {lang.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Style chips */}
          <div>
            <p style={{
              margin: '0 0 6px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--c-muted)',
              letterSpacing: '0.08em',
            }}>STYLE</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {STYLES.map((style) => {
                const active = selectedStyles.includes(style)
                return (
                  <button
                    key={style}
                    onClick={() => toggleStyle(style)}
                    style={{
                      height: 32,
                      padding: '0 10px',
                      border: `1.5px solid ${active ? 'var(--c-gold)' : 'var(--c-border)'}`,
                      background: active ? 'var(--c-gold-bg)' : 'var(--c-surface)',
                      color: active ? 'var(--c-gold-text)' : 'var(--c-muted)',
                      borderRadius: 5,
                      cursor: 'pointer',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.62rem',
                      fontWeight: active ? 600 : 400,
                      transition: 'all 0.15s',
                    }}
                  >
                    {style}
                  </button>
                )
              })}
            </div>
          </div>

          {error && (
            <p style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: '0.62rem', color: 'var(--c-red)' }}>
              {error}
            </p>
          )}

          {/* Generate button */}
          <button
            onClick={generating ? undefined : handleGenerate}
            disabled={generating}
            style={{
              height: 44,
              width: '100%',
              background: generating ? 'rgba(200,137,10,0.5)' : 'var(--c-gold)',
              border: 'none',
              borderRadius: 6,
              color: generating ? 'rgba(255,255,255,0.7)' : '#fff',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.72rem',
              fontWeight: 700,
              letterSpacing: '0.12em',
              cursor: generating ? 'not-allowed' : 'pointer',
              transition: 'background 0.2s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
            }}
          >
            {generating ? (
              <>
                <span style={{ animation: 'pulse-dot 1s ease-in-out infinite' }}>●</span>
                GENERATING…
              </>
            ) : 'GENERATE SCRIPT'}
          </button>
        </div>
      )}

      {/* Script drafted state: show ScriptReview */}
      {isDrafted && (
        <div>
          <ScriptReview
            videoId={video.video_id}
            onApproved={onRefresh}
            onRefresh={onRefresh}
          />
        </div>
      )}
    </div>
  )
}
