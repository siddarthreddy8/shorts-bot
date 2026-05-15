import { useEffect, useState } from 'react'
import { approveScript, fetchScript, fetchSeo, fetchTranscript, generateSeo, regenerateScript } from '../lib/api'
import type { DraftScript, SeoMetadata } from '../lib/types'
import { SeoPanel } from './SeoPanel'

const label: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '0.6rem',
  color: 'var(--c-muted)',
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  display: 'block',
  marginBottom: 7,
}

const inputBase: React.CSSProperties = {
  width: '100%',
  background: 'var(--c-surface)',
  border: '1px solid var(--c-border)',
  borderRadius: 5,
  color: 'var(--c-text)',
  fontFamily: 'var(--font-sans)',
  fontSize: '0.85rem',
  lineHeight: 1.65,
  padding: '9px 12px',
  boxSizing: 'border-box',
}

export function ScriptReview({
  videoId,
  onApproved,
  onRefresh,
}: {
  videoId: string
  onApproved: () => void
  onRefresh: () => void
}) {
  const [draft, setDraft] = useState<DraftScript | null>(null)
  const [hookIdx, setHookIdx] = useState(0)
  const [body, setBody] = useState('')
  const [cta, setCta] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [transcriptOpen, setTranscriptOpen] = useState(false)
  const [transcript, setTranscript] = useState<string | null>(null)
  const [transcriptLoading, setTranscriptLoading] = useState(false)
  const [seo, setSeo] = useState<SeoMetadata | null>(null)
  const [seoLoading, setSeoLoading] = useState(false)
  const [seoRegenerating, setSeoRegenerating] = useState(false)
  const [seoFailed, setSeoFailed] = useState(false)

  useEffect(() => {
    setLoading(true)
    setSeo(null)
    setSeoLoading(true)
    setSeoFailed(false)

    fetchScript(videoId)
      .then((d) => {
        setDraft(d)
        setBody(d.body)
        setCta(d.cta)
        setLoading(false)
      })
      .catch(() => setLoading(false))

    fetchSeo(videoId)
      .then((data) => {
        setSeo(data)
        setSeoLoading(false)
      })
      .catch(() => {
        generateSeo(videoId)
          .then((data) => {
            setSeo(data)
            setSeoLoading(false)
          })
          .catch(() => {
            setSeoLoading(false)
            setSeoFailed(true)
          })
      })
  }, [videoId])

  if (loading || !draft) {
    return (
      <p style={{ color: 'var(--c-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', marginTop: 14 }}>
        Loading draft…
      </p>
    )
  }

  const wc = `${draft.hooks[hookIdx]} ${body} ${cta}`.split(/\s+/).filter(Boolean).length
  const wcOk = wc >= 350 && wc <= 450

  const handleApprove = async () => {
    setSubmitting(true)
    try {
      await approveScript(videoId, draft.hooks[hookIdx], body, cta, seo ?? undefined)
      onApproved()
    } catch {
      setSubmitting(false)
    }
  }

  const handleRegenerate = async () => {
    setRegenerating(true)
    try {
      await regenerateScript(videoId)
      onRefresh()
    } catch {
      setRegenerating(false)
    }
  }

  const handleRegenerateSeo = async () => {
    setSeoRegenerating(true)
    setSeoFailed(false)
    try {
      const data = await generateSeo(videoId)
      setSeo(data)
    } catch {
      setSeoFailed(true)
    } finally {
      setSeoRegenerating(false)
    }
  }

  const handleToggleTranscript = async () => {
    if (!transcriptOpen && transcript === null) {
      setTranscriptLoading(true)
      try {
        const text = await fetchTranscript(videoId)
        setTranscript(text)
      } catch {
        setTranscript('')
      } finally {
        setTranscriptLoading(false)
      }
    }
    setTranscriptOpen((v) => !v)
  }

  return (
    <div style={{ marginTop: 14, borderTop: '1px solid var(--c-border-sub)', paddingTop: 14, display: 'flex', flexDirection: 'column', gap: 13, animation: 'slide-in 0.18s ease-out' }}>

      {/* Metadata row */}
      {(draft.language || draft.styles?.length > 0) && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {draft.language && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-blue)', background: 'var(--c-blue-bg)', border: '1px solid var(--c-blue-border)', padding: '2px 8px', borderRadius: 3 }}>
              {draft.language.toUpperCase()}
            </span>
          )}
          {draft.styles?.map((s) => (
            <span key={s} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)', background: 'var(--c-surface)', border: '1px solid var(--c-border)', padding: '2px 8px', borderRadius: 3 }}>
              {s}
            </span>
          ))}
        </div>
      )}

      {/* Hook selector */}
      <div>
        <span style={label}>Hook — pick one</span>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 7 }}>
          {draft.hooks.map((h, i) => (
            <button
              key={i}
              onClick={() => setHookIdx(i)}
              style={{
                background: i === hookIdx ? 'var(--c-gold-bg)' : 'var(--c-surface)',
                border: `1.5px solid ${i === hookIdx ? 'var(--c-gold)' : 'var(--c-border)'}`,
                borderRadius: 5,
                padding: '9px 11px',
                color: i === hookIdx ? 'var(--c-gold-text)' : 'var(--c-text2)',
                fontSize: '0.82rem',
                textAlign: 'left',
                cursor: 'pointer',
                lineHeight: 1.5,
                transition: 'all 0.15s',
                fontFamily: 'var(--font-sans)',
                minHeight: 44,
              }}
            >
              {h}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div>
        <span style={label}>Body</span>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
          style={{ ...inputBase, resize: 'vertical' }}
        />
      </div>

      {/* CTA */}
      <div>
        <span style={label}>CTA</span>
        <input
          value={cta}
          onChange={(e) => setCta(e.target.value)}
          style={inputBase}
        />
      </div>

      {/* SEO panel */}
      {seoLoading && (
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--c-muted)' }}>
          Generating SEO…
        </p>
      )}
      {seoFailed && !seoLoading && (
        <div style={{ borderTop: '1px solid var(--c-border-sub)', paddingTop: 14 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)', letterSpacing: '0.12em', textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>
            SEO Metadata
          </span>
          <button
            onClick={handleRegenerateSeo}
            style={{
              background: 'none',
              border: '1px solid var(--c-border)',
              borderRadius: 4,
              color: 'var(--c-text2)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              letterSpacing: '0.06em',
              padding: '6px 12px',
              cursor: 'pointer',
            }}
          >
            Generate SEO
          </button>
        </div>
      )}
      {seo && !seoLoading && (
        <SeoPanel
          seo={seo}
          onChange={setSeo}
          onRegenerate={handleRegenerateSeo}
          regenerating={seoRegenerating}
        />
      )}

      {/* Footer */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.68rem',
          fontWeight: 500,
          color: wcOk ? 'var(--c-green)' : 'var(--c-red)',
          flexShrink: 0,
        }}>
          {wc} words {wcOk ? '✓' : '(350–450)'}
        </span>
        <button
          onClick={handleRegenerate}
          disabled={regenerating || submitting}
          style={{
            background: 'var(--c-surface)',
            border: '1px solid var(--c-border)',
            color: 'var(--c-text2)',
            padding: '10px 14px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.65rem',
            letterSpacing: '0.06em',
            borderRadius: 4,
            cursor: regenerating ? 'not-allowed' : 'pointer',
            opacity: regenerating ? 0.6 : 1,
            whiteSpace: 'nowrap',
            minHeight: 44,
          }}
        >
          {regenerating ? '↺ Working…' : '↺ Regenerate'}
        </button>
        <button
          onClick={handleApprove}
          disabled={submitting || regenerating}
          style={{
            flex: 1,
            minWidth: 120,
            background: submitting ? 'var(--c-border)' : 'var(--c-gold)',
            color: submitting ? 'var(--c-muted)' : '#fff',
            border: 'none',
            padding: '10px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            fontWeight: 600,
            letterSpacing: '0.1em',
            cursor: submitting ? 'not-allowed' : 'pointer',
            borderRadius: 4,
            boxShadow: submitting ? 'none' : '0 1px 6px rgba(200,137,10,0.3)',
            minHeight: 44,
          }}
        >
          {submitting ? 'STARTING…' : 'APPROVE & RUN'}
        </button>
      </div>
      {/* Source transcript (collapsible) */}
      <div style={{ borderTop: '1px solid var(--c-border-sub)', paddingTop: 10 }}>
        <button
          onClick={handleToggleTranscript}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: 0,
          }}
        >
          <span style={{ fontSize: '0.6rem', color: 'var(--c-muted)' }}>{transcriptOpen ? '▾' : '▸'}</span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)', letterSpacing: '0.1em' }}>
            {transcriptLoading ? 'LOADING…' : 'SOURCE TRANSCRIPT'}
          </span>
        </button>
        {transcriptOpen && transcript !== null && (
          <pre style={{
            marginTop: 8,
            padding: '10px 12px',
            background: 'var(--c-surface)',
            border: '1px solid var(--c-border-sub)',
            borderRadius: 4,
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: 'var(--c-text2)',
            lineHeight: 1.7,
            maxHeight: 220,
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
            {transcript || 'No transcript text found.'}
          </pre>
        )}
      </div>
    </div>
  )
}
