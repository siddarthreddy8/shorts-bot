import { useEffect, useState } from 'react'
import { fetchStatus } from '../lib/api'
import type { PipelineStatus, VideoStatus } from '../lib/types'

const IN_PROGRESS: PipelineStatus[] = ['script_approved', 'video_rendered']

export function useVideoStatus(videoId: string, status: PipelineStatus) {
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null)

  useEffect(() => {
    if (!IN_PROGRESS.includes(status)) {
      setVideoStatus(null)
      return
    }
    let active = true
    const poll = async () => {
      try {
        const data = await fetchStatus(videoId)
        if (active) setVideoStatus(data)
      } catch { /* retry next interval */ }
    }
    poll()
    const id = setInterval(poll, 2000)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [videoId, status])

  return videoStatus
}
