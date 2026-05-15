import type { Channel, Costs, DraftScript, PipelineEvent, Stats, Video, VideoStatus } from './types'

const BASE = '/api'

async function post(path: string, body?: unknown): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
}

async function apiPost(path: string, body?: unknown): Promise<void> {
  let r: Response
  try {
    r = await post(path, body)
  } catch {
    throw new Error('SERVER_DOWN')
  }
  if (!r.ok) {
    const text = await r.text().catch(() => '')
    throw new Error(`HTTP_${r.status}:${text.slice(0, 120)}`)
  }
}

// ── Videos ───────────────────────────────────────────────────────────────────

export async function fetchVideos(): Promise<Video[]> {
  const r = await fetch(`${BASE}/videos`)
  if (!r.ok) throw new Error('Failed to fetch videos')
  return r.json()
}

export async function fetchScript(videoId: string): Promise<DraftScript> {
  const r = await fetch(`${BASE}/videos/${videoId}/script`)
  if (!r.ok) throw new Error('No draft script')
  return r.json()
}

export async function approveScript(videoId: string, hook: string, body: string, cta: string): Promise<void> {
  const r = await post(`/videos/${videoId}/approve`, { hook, body, cta })
  if (!r.ok) throw new Error('Approve failed')
}

export async function fetchStatus(videoId: string): Promise<VideoStatus> {
  const r = await fetch(`${BASE}/videos/${videoId}/status`)
  if (!r.ok) throw new Error('Status fetch failed')
  return r.json()
}

export function previewUrl(videoId: string): string {
  return `${BASE}/videos/${videoId}/preview`
}

export async function publishVideo(videoId: string): Promise<void> {
  const r = await post(`/videos/${videoId}/publish`)
  if (!r.ok) throw new Error('Publish failed')
}

export async function rejectRender(videoId: string): Promise<void> {
  const r = await post(`/videos/${videoId}/reject-render`)
  if (!r.ok) throw new Error('Reject failed')
}

export async function regenerateScript(videoId: string): Promise<void> {
  const r = await post(`/videos/${videoId}/regenerate-script`)
  if (!r.ok) throw new Error('Regenerate failed')
}

export async function retryVideo(videoId: string): Promise<void> {
  const r = await post(`/videos/${videoId}/retry`)
  if (!r.ok) throw new Error('Retry failed')
}

export async function dismissVideo(videoId: string): Promise<void> {
  const r = await post(`/videos/${videoId}/dismiss`)
  if (!r.ok) throw new Error('Dismiss failed')
}

export async function fetchTranscript(videoId: string): Promise<string> {
  const r = await fetch(`${BASE}/videos/${videoId}/transcript`)
  if (!r.ok) throw new Error('No transcript')
  const data = await r.json()
  return data.text
}

// ── Dashboard data ────────────────────────────────────────────────────────────

export async function fetchStats(): Promise<Stats> {
  const r = await fetch(`${BASE}/stats`)
  if (!r.ok) throw new Error('Stats fetch failed')
  return r.json()
}

export async function fetchChannels(): Promise<Channel[]> {
  const r = await fetch(`${BASE}/channels`)
  if (!r.ok) throw new Error('Channels fetch failed')
  return r.json()
}

export async function fetchCosts(): Promise<Costs> {
  const r = await fetch(`${BASE}/costs`)
  if (!r.ok) throw new Error('Costs fetch failed')
  return r.json()
}

export async function fetchEvents(limit = 20): Promise<PipelineEvent[]> {
  const r = await fetch(`${BASE}/events?limit=${limit}`)
  if (!r.ok) throw new Error('Events fetch failed')
  return r.json()
}

// ── Actions ───────────────────────────────────────────────────────────────────

export async function triggerMonitor(): Promise<void> {
  await post('/actions/monitor')
}

export async function triggerRun(): Promise<void> {
  await post('/actions/run')
}

export async function ingestUrl(url: string, language = 'english', styles = ['documentary']): Promise<void> {
  await post('/actions/ingest', { url, language, styles })
}

export async function generateScript(videoId: string, language: string, styles: string[]): Promise<void> {
  await apiPost(`/videos/${videoId}/generate-script`, { language, styles })
}
