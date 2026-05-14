import { useEffect, useState } from 'react'
import { fetchVideos } from '../lib/api'
import type { Video } from '../lib/types'

export function useVideos(intervalMs = 5000) {
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)

  const refresh = () => setTick((t) => t + 1)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const data = await fetchVideos()
        if (active) setVideos(data)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    const id = setInterval(load, intervalMs)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [intervalMs, tick])

  return { videos, loading, refresh }
}
