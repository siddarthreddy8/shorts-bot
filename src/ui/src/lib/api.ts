import type { DraftScript, Video, VideoStatus } from './types'

const BASE = '/api'

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

export async function approveScript(
  videoId: string,
  hook: string,
  body: string,
  cta: string,
): Promise<void> {
  const r = await fetch(`${BASE}/videos/${videoId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hook, body, cta }),
  })
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
