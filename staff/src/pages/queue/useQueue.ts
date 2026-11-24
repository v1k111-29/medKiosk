import { useCallback, useEffect, useMemo, useState } from 'react'
import { errorMessage, wsUrl } from '../../api/client'
import { fetchQueue } from '../../api/queue'
import type { QueueCounts, QueueItem, QueueStatus, QueueWsMessage } from '../../api/types'
import { useReconnectingSocket } from '../../hooks/useReconnectingSocket'
import { tokenNumber } from '../../lib/format'
import { useAuth } from '../../store/auth'

const URGENCY_RANK = { emergency: 0, urgent: 1, normal: 2 } as const

function sortItems(items: QueueItem[]): QueueItem[] {
  return [...items].sort(
    (a, b) =>
      URGENCY_RANK[a.urgency] - URGENCY_RANK[b.urgency] ||
      tokenNumber(a.token) - tokenNumber(b.token) ||
      a.appointment_id - b.appointment_id,
  )
}

export const EMPTY_COUNTS: QueueCounts = { waiting: 0, called: 0, in_consult: 0, done: 0, no_show: 0 }

function isQueueMessage(msg: unknown): msg is QueueWsMessage {
  return typeof msg === 'object' && msg !== null && (msg as { type?: unknown }).type === 'queue.updated'
}

export interface UseQueue {
  items: QueueItem[]
  counts: QueueCounts
  connected: boolean
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  upsert: (item: QueueItem) => void
}

/** Today's queue for one department (or all), kept fresh by WS with 15s polling fallback. */
export function useQueue(deptId: string): UseQueue {
  const token = useAuth((s) => s.token)
  const [all, setAll] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await fetchQueue(deptId || undefined)
      setAll(sortItems(res.items))
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [deptId])

  useEffect(() => {
    setLoading(true)
    void refresh()
  }, [refresh])

  const upsert = useCallback(
    (item: QueueItem) => {
      if (deptId && item.dept_id !== deptId) return
      setAll((prev) => {
        const without = prev.filter((p) => p.appointment_id !== item.appointment_id)
        return sortItems([...without, item])
      })
    },
    [deptId],
  )

  const connected = useReconnectingSocket(
    token ? wsUrl('/ws/queue', { token }) : null,
    (msg) => {
      if (isQueueMessage(msg)) upsert(msg.data)
    },
    () => void refresh(),
  )

  useEffect(() => {
    if (connected) return
    const id = window.setInterval(() => void refresh(), 15000)
    return () => window.clearInterval(id)
  }, [connected, refresh])

  const counts = useMemo(() => {
    const c: QueueCounts = { ...EMPTY_COUNTS }
    for (const it of all) c[it.status as QueueStatus] += 1
    return c
  }, [all])

  return { items: all, counts, connected, loading, error, refresh, upsert }
}
