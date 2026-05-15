import type { SeoMetadata } from '../lib/types'

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

export function SeoPanel({
  seo,
  onChange,
  onRegenerate,
  regenerating,
}: {
  seo: SeoMetadata
  onChange: (updated: SeoMetadata) => void
  onRegenerate: () => void
  regenerating: boolean
}) {
  const titleLen = seo.title.length
  const titleOk = titleLen <= 60

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>

      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--c-border-sub)', paddingTop: 14 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          SEO Metadata
        </span>
        <button
          onClick={onRegenerate}
          disabled={regenerating}
          style={{
            background: 'none',
            border: '1px solid var(--c-border)',
            borderRadius: 4,
            color: 'var(--c-text2)',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.6rem',
            letterSpacing: '0.06em',
            padding: '4px 10px',
            cursor: regenerating ? 'not-allowed' : 'pointer',
            opacity: regenerating ? 0.6 : 1,
          }}
        >
          {regenerating ? '↺ Working…' : '↺ Regenerate'}
        </button>
      </div>

      {/* Title */}
      <div>
        <span style={label}>
          Title{' '}
          <span style={{ color: titleOk ? 'var(--c-green)' : 'var(--c-red)' }}>
            {titleLen}/60
          </span>
        </span>
        <input
          value={seo.title}
          onChange={(e) => onChange({ ...seo, title: e.target.value })}
          style={{ ...inputBase, borderColor: titleOk ? 'var(--c-border)' : 'var(--c-red)' }}
        />
      </div>

      {/* Description */}
      <div>
        <span style={label}>Description</span>
        <textarea
          value={seo.description}
          onChange={(e) => onChange({ ...seo, description: e.target.value })}
          rows={5}
          style={{ ...inputBase, resize: 'vertical' }}
        />
      </div>

      {/* Hashtags */}
      <div>
        <span style={label}>Hashtags — one per line</span>
        <textarea
          value={seo.hashtags.join('\n')}
          onChange={(e) =>
            onChange({
              ...seo,
              hashtags: e.target.value.split('\n').map((t) => t.trim()).filter(Boolean),
            })
          }
          rows={6}
          style={{
            ...inputBase,
            resize: 'vertical',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
          }}
        />
      </div>

      {/* Thumbnail phrase */}
      {seo.thumbnail_phrases.length > 0 && (
        <div>
          <span style={label}>Thumbnail phrase</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {seo.thumbnail_phrases.map((phrase) => (
              <label
                key={phrase}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  padding: '8px 10px',
                  borderRadius: 5,
                  background: seo.thumbnail_phrase === phrase ? 'var(--c-gold-bg)' : 'var(--c-surface)',
                  border: `1.5px solid ${seo.thumbnail_phrase === phrase ? 'var(--c-gold)' : 'var(--c-border)'}`,
                  transition: 'all 0.15s',
                }}
              >
                <input
                  type="radio"
                  name={`thumbnail_phrase_${seo.thumbnail_phrases.join('')}`}
                  value={phrase}
                  checked={seo.thumbnail_phrase === phrase}
                  onChange={() => onChange({ ...seo, thumbnail_phrase: phrase })}
                  style={{ accentColor: 'var(--c-gold)', flexShrink: 0 }}
                />
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: '0.82rem', color: 'var(--c-text)' }}>
                  {phrase}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
