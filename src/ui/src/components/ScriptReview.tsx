import { useEffect, useState } from 'react'
import { approveScript, fetchScript } from '../lib/api'
import type { DraftScript } from '../lib/types'

export function ScriptReview({
  videoId,
  onApproved,
}: {
  videoId: string
  onApproved: () => void
}) {
  const [draft, setDraft] = useState<DraftScript | null>(null)
  const [hookIdx, setHookIdx] = useState(0)
  const [body, setBody] = useState('')
  const [cta, setCta] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetchScript(videoId).then((d) => {
      setDraft(d)
      setBody(d.body)
      setCta(d.cta)
      setLoading(false)
    })
  }, [videoId])

  if (loading || !draft) {
    return (
      <p style={{ color: 'var(--c-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', marginTop: 16 }}>
        Loading draft…
      </p>
    )
  }

  const wc = `${draft.hooks[hookIdx]} ${body} ${cta}`.split(/\s+/).filter(Boolean).length
  const wcOk = wc >= 350 && wc <= 450

  const handleApprove = async () => {
    setSubmitting(true)
    try {
      await approveScript(videoId, draft.hooks[hookIdx], body, cta)
      onApproved()
    } catch {
      setSubmitting(false)
    }
  }

  const labelStyle: React.CSSProperties = {
    fontFamily: 'var(--font-mono)',
    fontSize: '0.63rem',
    color: 'var(--c-muted)',
    letterSpacing: '0.1em',
    display: 'block',
    marginBottom: 8,
  }

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: 'var(--c-surface)',
    border: '1px solid var(--c-border)',
    borderRadius: 4,
    color: 'var(--c-text)',
    fontFamily: 'var(--font-sans)',
    fontSize: '0.88rem',
    padding: '10px 12px',
    boxSizing: 'border-box',
    lineHeight: 1.6,
  }

  return (
    <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 18 }}>

      {/* Hook selector */}
      <div>
        <span style={labelStyle}>HOOK — pick one</span>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
          {draft.hooks.map((h, i) => (
            <button
              key={i}
              onClick={() => setHookIdx(i)}
              style={{
                background: i === hookIdx ? 'rgba(255,217,61,0.07)' : 'var(--c-surface)',
                border: `1px solid ${i === hookIdx ? 'var(--c-gold)' : 'var(--c-border)'}`,
                borderRadius: 4,
                padding: '10px 12px',
                color: i === hookIdx ? 'var(--c-gold)' : 'var(--c-text)',
                fontSize: '0.82rem',
                textAlign: 'left',
                cursor: 'pointer',
                lineHeight: 1.45,
                boxShadow: i === hookIdx ? '0 0 14px rgba(255,217,61,0.12)' : 'none',
                transition: 'all 0.15s',
              }}
            >
              {h}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div>
        <span style={labelStyle}>BODY</span>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={14}
          style={{ ...inputStyle, resize: 'vertical' }}
        />
      </div>

      {/* CTA */}
      <div>
        <span style={labelStyle}>CTA</span>
        <input value={cta} onChange={(e) => setCta(e.target.value)} style={inputStyle} />
      </div>

      {/* Word count + approve */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.72rem',
          color: wcOk ? 'var(--c-green)' : 'var(--c-red)',
          flexShrink: 0,
        }}>
          {wc} words {wcOk ? '✓' : '(350–450)'}
        </span>
        <button
          onClick={handleApprove}
          disabled={submitting}
          style={{
            flex: 1,
            background: submitting ? 'var(--c-border)' : 'var(--c-gold)',
            color: '#000',
            border: 'none',
            padding: '13px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.78rem',
            fontWeight: 600,
            letterSpacing: '0.12em',
            cursor: submitting ? 'not-allowed' : 'pointer',
            borderRadius: 2,
            transition: 'opacity 0.15s',
          }}
        >
          {submitting ? 'STARTING PIPELINE…' : 'APPROVE & RUN'}
        </button>
      </div>
    </div>
  )
}
