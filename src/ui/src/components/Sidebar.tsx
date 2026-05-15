import { useState } from 'react'
import { generateScript, ingestUrl, publishVideo, toggleChannel, triggerMonitor, triggerRun } from '../lib/api'
import type { Channel, Video } from '../lib/types'
import { useChannels } from '../hooks/useChannels'
import { useCosts } from '../hooks/useCosts'
import { useStats } from '../hooks/useStats'

const USD_TO_INR = 85.5

const sectionLabel: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '0.58rem',
  color: 'var(--c-muted)',
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  marginBottom: 10,
  display: 'block',
}

const divider: React.CSSProperties = {
  borderTop: '1px solid var(--c-border-sub)',
  margin: '0',
}

function SidebarSection({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{ padding: '13px 16px', ...style }}>
      {children}
    </div>
  )
}

function MetricPill({
  value, label, variant,
}: {
  value: number
  label: string
  variant?: 'gold' | 'blue' | 'green' | 'red' | 'default'
}) {
  const colors: Record<string, { num: string; bg: string; border: string }> = {
    gold:    { num: 'var(--c-gold)',  bg: 'var(--c-gold-bg)',   border: 'var(--c-gold-border)' },
    blue:    { num: 'var(--c-blue)',  bg: 'var(--c-blue-bg)',   border: 'var(--c-blue-border)' },
    green:   { num: 'var(--c-green)', bg: 'var(--c-green-bg)',  border: 'var(--c-green-border)' },
    red:     { num: 'var(--c-red)',   bg: 'var(--c-red-bg)',    border: 'var(--c-red-border)' },
    default: { num: 'var(--c-text)',  bg: 'var(--c-surface)',   border: 'var(--c-border-sub)' },
  }
  const c = colors[variant ?? 'default']
  return (
    <div style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 6, padding: '8px 10px' }}>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.35rem', fontWeight: 700, color: c.num, lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--c-muted)', letterSpacing: '0.08em', marginTop: 3 }}>
        {label}
      </div>
    </div>
  )
}

const STAGE_ORDER = [
  { key: 'discovered',      label: 'Discovered',  action: null },
  { key: 'transcribed',     label: 'Transcribed', action: 'Generate' },
  { key: 'script_drafted',  label: 'Drafted',     action: null },
  { key: 'script_approved', label: 'Approved',    action: null },
  { key: 'video_rendered',  label: 'Rendered',    action: 'Publish All' },
  { key: 'uploaded',        label: 'Uploaded',    action: null },
]

function timeAgo(iso: string | null): string {
  if (!iso) return 'never'
  const diff = (Date.now() - new Date(iso + 'Z').getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

export function Sidebar({ onClose, videos = [], onRefresh }: { onClose?: () => void; videos?: Video[]; onRefresh?: () => void }) {
  const stats = useStats()
  const fetchedChannels = useChannels()
  const [localChannels, setLocalChannels] = useState<Channel[] | null>(null)
  const channels = localChannels ?? fetchedChannels
  const costs = useCosts()
  const [url, setUrl] = useState('')
  const [urlLoading, setUrlLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [bulkProgress, setBulkProgress] = useState<{ done: number; total: number } | null>(null)
  const [togglingChannel, setTogglingChannel] = useState<string | null>(null)

  const handleToggleChannel = async (channelId: string) => {
    setTogglingChannel(channelId)
    try {
      const result = await toggleChannel(channelId)
      setLocalChannels((prev) =>
        (prev ?? fetchedChannels).map((ch) =>
          ch.channel_id === channelId ? { ...ch, enabled: result.enabled ? 1 : 0 } : ch
        )
      )
    } finally {
      setTogglingChannel(null)
    }
  }

  const handleIngest = async () => {
    if (!url.trim()) return
    setUrlLoading(true)
    try { await ingestUrl(url.trim()) } finally { setUrlLoading(false); setUrl('') }
  }

  const handleMonitor = async () => {
    setActionLoading('monitor')
    try { await triggerMonitor() } finally { setActionLoading(null) }
  }

  const handleRun = async () => {
    setActionLoading('run')
    try { await triggerRun() } finally { setActionLoading(null) }
  }

  const handleGenerateAll = async () => {
    const targets = videos.filter((v) => v.status === 'transcribed')
    if (targets.length === 0) return
    setBulkProgress({ done: 0, total: targets.length })
    for (let i = 0; i < targets.length; i++) {
      try { await generateScript(targets[i].video_id, 'english', ['documentary']) } catch { /* continue */ }
      setBulkProgress({ done: i + 1, total: targets.length })
    }
    setBulkProgress(null)
    onRefresh?.()
  }

  const handlePublishAll = async () => {
    const targets = videos.filter((v) => v.status === 'video_rendered')
    if (targets.length === 0) return
    setBulkProgress({ done: 0, total: targets.length })
    for (let i = 0; i < targets.length; i++) {
      try { await publishVideo(targets[i].video_id) } catch { /* continue */ }
      setBulkProgress({ done: i + 1, total: targets.length })
    }
    setBulkProgress(null)
    onRefresh?.()
  }

  const byStage = stats?.by_stage ?? {}
  const topStyle = byStage.documentary ?? 0
  const maxStyle = Math.max(1, ...Object.values(byStage))

  const styleEntries = [
    { label: 'Documentary', count: byStage.documentary ?? 0 },
    { label: 'Storytelling', count: byStage.storytelling ?? 0 },
    { label: 'Comedy', count: byStage.comedy ?? 0 },
    { label: 'Explainer', count: byStage.explainer ?? 0 },
    { label: 'Serious', count: byStage.serious ?? 0 },
  ].filter((s) => s.count > 0).sort((a, b) => b.count - a.count).slice(0, 5)

  // Use pipeline stage counts from stats.by_stage
  const stageCounts: Record<string, number> = byStage

  return (
    <div style={{
      width: '100%',
      height: '100%',
      background: 'var(--c-sidebar)',
      borderLeft: '3px solid var(--c-gold)',
      display: 'flex',
      flexDirection: 'column',
      overflowY: 'auto',
      overflowX: 'hidden',
    }}>
      {/* Brand */}
      <div style={{ padding: '18px 16px 14px', borderBottom: '1px solid var(--c-border-sub)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem', fontWeight: 700, letterSpacing: '0.2em', color: 'var(--c-gold)' }}>
            SHORTS BOT
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--c-muted)', letterSpacing: '0.12em', marginTop: 3 }}>
            PIPELINE DASHBOARD
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--c-muted)', fontSize: '1.1rem', cursor: 'pointer', padding: '4px 6px', lineHeight: 1, minWidth: 36, minHeight: 36 }}
            aria-label="Close sidebar"
          >
            ✕
          </button>
        )}
      </div>

      {/* Metrics */}
      <SidebarSection>
        <span style={sectionLabel}>Overview</span>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
          <MetricPill value={stats?.total ?? 0} label="Total" />
          <MetricPill value={stats?.needs_review ?? 0} label="Need Review" variant="gold" />
          <MetricPill value={stats?.running ?? 0} label="Running" variant="blue" />
          <MetricPill value={stats?.uploaded ?? 0} label="Uploaded" variant="green" />
        </div>
        {(stats?.failed ?? 0) > 0 && (
          <div style={{ marginTop: 5 }}>
            <MetricPill value={stats!.failed} label="Failed" variant="red" />
          </div>
        )}
      </SidebarSection>

      <div style={divider} />

      {/* Pipeline stages */}
      <SidebarSection>
        <span style={sectionLabel}>Pipeline Stages</span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {STAGE_ORDER.map(({ key, label, action }) => {
            const count = stageCounts[key] ?? 0
            const isActive = count > 0 && key !== 'uploaded'
            return (
              <div key={key} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '5px 7px',
                borderRadius: 4,
                background: isActive ? 'var(--c-gold-bg)' : 'transparent',
                border: `1px solid ${isActive ? 'var(--c-gold-border)' : 'transparent'}`,
              }}>
                <span style={{
                  width: 5,
                  height: 5,
                  borderRadius: '50%',
                  background: key === 'uploaded' ? 'var(--c-green)' : isActive ? 'var(--c-gold)' : 'var(--c-muted2)',
                  flexShrink: 0,
                }} />
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.62rem',
                  color: isActive ? 'var(--c-gold-text)' : 'var(--c-muted)',
                  fontWeight: isActive ? 500 : 400,
                  flex: 1,
                }}>
                  {label}
                </span>
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  color: isActive ? 'var(--c-gold)' : 'var(--c-muted2)',
                }}>
                  {count}
                </span>
                {action && count > 0 && (() => {
                  const isBusy = bulkProgress !== null
                  const isThisAction = isBusy && (
                    (action === 'Generate'    && videos.some((v) => v.status === 'transcribed')) ||
                    (action === 'Publish All' && videos.some((v) => v.status === 'video_rendered'))
                  )
                  const label = isThisAction && bulkProgress
                    ? `${action === 'Generate' ? 'Gen' : 'Pub'} ${bulkProgress.done}/${bulkProgress.total}`
                    : action
                  return (
                    <button
                      disabled={isBusy}
                      onClick={action === 'Generate' ? handleGenerateAll : handlePublishAll}
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.55rem',
                        background: isBusy ? 'var(--c-surface)' : '#fff',
                        border: '1px solid var(--c-border)',
                        color: isBusy ? 'var(--c-muted)' : 'var(--c-text2)',
                        padding: '2px 6px',
                        borderRadius: 3,
                        cursor: isBusy ? 'not-allowed' : 'pointer',
                        whiteSpace: 'nowrap',
                        minHeight: 22,
                      }}
                    >
                      {label}
                    </button>
                  )
                })()}
              </div>
            )
          })}
        </div>
      </SidebarSection>

      <div style={divider} />

      {/* Actions */}
      <SidebarSection>
        <span style={sectionLabel}>Actions</span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button
            onClick={handleRun}
            disabled={actionLoading !== null}
            style={{
              background: actionLoading === 'run' ? 'var(--c-border)' : 'var(--c-gold)',
              color: actionLoading === 'run' ? 'var(--c-muted)' : '#fff',
              border: 'none',
              padding: '10px 14px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.65rem',
              fontWeight: 600,
              letterSpacing: '0.1em',
              borderRadius: 4,
              cursor: actionLoading !== null ? 'not-allowed' : 'pointer',
              boxShadow: actionLoading ? 'none' : '0 1px 6px rgba(200,137,10,0.28)',
              minHeight: 44,
            }}
          >
            {actionLoading === 'run' ? '▶ RUNNING…' : '▶ RUN FULL PIPELINE'}
          </button>
          <button
            onClick={handleMonitor}
            disabled={actionLoading !== null}
            style={{
              background: 'var(--c-surface)',
              border: '1px solid var(--c-border)',
              color: 'var(--c-text2)',
              padding: '9px 14px',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.65rem',
              letterSpacing: '0.08em',
              borderRadius: 4,
              cursor: actionLoading !== null ? 'not-allowed' : 'pointer',
              minHeight: 44,
            }}
          >
            {actionLoading === 'monitor' ? '⚡ Polling…' : '⚡ POLL CHANNELS'}
          </button>
        </div>
      </SidebarSection>

      <div style={divider} />

      {/* URL input */}
      <SidebarSection>
        <span style={sectionLabel}>Add Video</span>
        <div style={{ display: 'flex', gap: 5 }}>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleIngest()}
            placeholder="youtube.com/watch?v=…"
            style={{
              flex: 1,
              background: 'var(--c-surface)',
              border: '1px solid var(--c-border)',
              borderRadius: 4,
              color: 'var(--c-text)',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.62rem',
              padding: '8px 10px',
              minHeight: 36,
            }}
          />
          <button
            onClick={handleIngest}
            disabled={!url.trim() || urlLoading}
            style={{
              background: url.trim() ? 'var(--c-gold)' : 'var(--c-surface)',
              border: '1px solid var(--c-border)',
              color: url.trim() ? '#fff' : 'var(--c-muted)',
              padding: '8px 12px',
              borderRadius: 4,
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
              fontWeight: 700,
              cursor: url.trim() ? 'pointer' : 'not-allowed',
              minHeight: 36,
              minWidth: 36,
            }}
          >
            {urlLoading ? '…' : '+'}
          </button>
        </div>
      </SidebarSection>

      <div style={divider} />

      {/* Channel health */}
      <SidebarSection>
        <span style={sectionLabel}>Channel Health</span>
        {channels.length === 0 && (
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.62rem', color: 'var(--c-muted2)' }}>
            No channels polled yet.
          </p>
        )}
        {channels.map((ch) => {
          const enabled = ch.enabled !== 0
          const fresh = ch.last_polled_at
            ? (Date.now() - new Date(ch.last_polled_at + 'Z').getTime()) < 6 * 3600 * 1000
            : false
          const isToggling = togglingChannel === ch.channel_id
          return (
            <div key={ch.channel_id} style={{ marginBottom: 10, opacity: enabled ? 1 : 0.5 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                <span style={{
                  width: 5,
                  height: 5,
                  borderRadius: '50%',
                  background: enabled && fresh ? 'var(--c-green)' : 'var(--c-muted2)',
                  flexShrink: 0,
                  boxShadow: enabled && fresh ? '0 0 5px rgba(22,163,74,0.4)' : 'none',
                }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--c-text)', fontWeight: 500, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {ch.name ?? ch.channel_id.slice(0, 20)}
                </span>
                <button
                  onClick={() => handleToggleChannel(ch.channel_id)}
                  disabled={isToggling}
                  title={enabled ? 'Disable channel' : 'Enable channel'}
                  style={{
                    flexShrink: 0,
                    width: 32,
                    height: 18,
                    borderRadius: 9,
                    border: 'none',
                    cursor: isToggling ? 'not-allowed' : 'pointer',
                    background: enabled ? 'var(--c-green)' : 'var(--c-muted2)',
                    position: 'relative',
                    transition: 'background 0.2s',
                    padding: 0,
                  }}
                >
                  <span style={{
                    position: 'absolute',
                    top: 2,
                    left: enabled ? 16 : 2,
                    width: 14,
                    height: 14,
                    borderRadius: '50%',
                    background: '#fff',
                    transition: 'left 0.2s',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
                  }} />
                </button>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--c-muted)', paddingLeft: 11 }}>
                {enabled ? `Polled ${timeAgo(ch.last_polled_at)}` : 'Disabled'}
              </div>
            </div>
          )
        })}
      </SidebarSection>

      <div style={divider} />

      {/* Cost tracker */}
      <SidebarSection>
        <span style={sectionLabel}>Estimated Cost</span>
        {costs ? (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)' }}>OpenRouter (AI)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--c-text2)' }}>₹{(costs.openrouter * USD_TO_INR).toFixed(2)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)' }}>ElevenLabs (TTS)</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--c-text2)' }}>₹{(costs.elevenlabs * USD_TO_INR).toFixed(2)}</span>
            </div>
            <div style={{ borderTop: '1px solid var(--c-border)', paddingTop: 7, display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)' }}>Total</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', fontWeight: 700, color: 'var(--c-gold)' }}>₹{(costs.total * USD_TO_INR).toFixed(2)}</span>
            </div>
            <div style={{ marginTop: 5, textAlign: 'right' }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.52rem', color: 'var(--c-muted2)' }}>1 USD = ₹{USD_TO_INR}</span>
            </div>
          </>
        ) : (
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.62rem', color: 'var(--c-muted2)' }}>Loading…</p>
        )}
      </SidebarSection>

      {/* Style distribution */}
      {styleEntries.length > 0 && (
        <>
          <div style={divider} />
          <SidebarSection style={{ paddingBottom: 16 }}>
            <span style={sectionLabel}>Style Distribution</span>
            {styleEntries.map(({ label, count }) => (
              <div key={label} style={{ marginBottom: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--c-muted)' }}>{label}</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--c-muted)' }}>{count}</span>
                </div>
                <div style={{ background: 'var(--c-surface)', borderRadius: 2, height: 3, overflow: 'hidden', border: '1px solid var(--c-border-sub)' }}>
                  <div style={{ height: '100%', borderRadius: 2, background: 'var(--c-gold)', width: `${(count / maxStyle) * 100}%` }} />
                </div>
              </div>
            ))}
          </SidebarSection>
        </>
      )}
    </div>
  )
}
