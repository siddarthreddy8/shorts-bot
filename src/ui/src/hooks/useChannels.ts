import { useEffect, useState } from 'react'
import { fetchChannels } from '../lib/api'
import type { Channel } from '../lib/types'

export function useChannels(intervalMs = 30000) {
  const [channels, setChannels] = useState<Channel[]>([])

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const data = await fetchChannels()
        if (active) setChannels(data)
      } catch { /* swallow */ }
    }
    load()
    const id = setInterval(load, intervalMs)
    return () => { active = false; clearInterval(id) }
  }, [intervalMs])

  return channels
}
