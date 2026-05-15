import { useEffect, useState } from 'react'
import { fetchStats } from '../lib/api'
import type { Stats } from '../lib/types'

export function useStats(intervalMs = 5000) {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const data = await fetchStats()
        if (active) setStats(data)
      } catch { /* swallow — retry next interval */ }
    }
    load()
    const id = setInterval(load, intervalMs)
    return () => { active = false; clearInterval(id) }
  }, [intervalMs])

  return stats
}
