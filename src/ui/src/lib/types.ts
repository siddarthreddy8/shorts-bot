export type PipelineStatus =
  | 'discovered' | 'transcribed' | 'script_drafted'
  | 'script_approved' | 'video_rendered' | 'uploaded'
  | 'failed' | 'skipped'

export type StepState = 'pending' | 'running' | 'done' | 'failed'

export interface Step {
  name: string
  state: StepState
  error: string | null
}

export interface Video {
  video_id: string
  source_title: string | null
  source_channel_name: string | null
  status: PipelineStatus
  updated_at: string
  youtube_url: string | null
  target_language: string | null
  styles_json: string | null
  failure_reason: string | null
}

export interface VideoStatus {
  status: PipelineStatus
  steps: Step[]
}

export interface DraftScript {
  hooks: string[]
  body: string
  cta: string
  word_count: number
  language: string
  styles: string[]
}

export interface Stats {
  total: number
  needs_review: number
  running: number
  ready_to_publish: number
  uploaded: number
  failed: number
  by_stage: Record<string, number>
}

export interface Channel {
  channel_id: string
  name: string | null
  last_polled_at: string | null
  last_seen_video_id: string | null
}

export interface Costs {
  openrouter: number
  elevenlabs: number
  total: number
  tts_chars: number
  scripts: number
}

export interface PipelineEvent {
  id: number
  video_id: string
  source_title: string | null
  stage: string
  level: string
  message: string
  created_at: string
}
