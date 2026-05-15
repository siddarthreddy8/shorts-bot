import { useEffect, useState } from 'react'
import { fetchCosts } from '../lib/api'
import type { Costs } from '../lib/types'

export function useCosts(intervalMs = 60000) {
  const [costs, setCosts] = useState<Costs | null>(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const data = await fetchCosts()
        if (active) setCosts(data)
      } catch { /* swallow */ }
    }
    load()
    const id = setInterval(load, intervalMs)
    return () => { active = false; clearInterval(id) }
  }, [intervalMs])

  return costs
}
