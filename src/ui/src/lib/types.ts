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
