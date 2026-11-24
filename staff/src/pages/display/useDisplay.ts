import { useCallback, useEffect, useState } from 'react'
import { wsUrl } from '../../api/client'
import { listDepartments } from '../../api/departments'
import { fetchNowServing } from '../../api/display'
import type { CalledToken, Department, DisplayWsMessage, WaitingCounts } from '../../api/types'
import { useReconnectingSocket } from '../../hooks/useReconnectingSocket'
import { announceToken } from '../../lib/announce'

const MAX_RECENT = 10

function isDisplayMessage(msg: unknown): msg is DisplayWsMessage {
  if (typeof msg !== 'object' || msg === null) return false
  const t = (msg as { type?: unknown }).type
  return t === 'token.called' || t === 'counts'
}

export interface UseDisplay {
  called: CalledToken[]
  counts: WaitingCounts
  departments: Department[]
  connected: boolean
}

export function useDisplay(deptId: string | null): UseDisplay {
  const [called, setCalled] = useState<CalledToken[]>([])
  const [counts, setCounts] = useState<WaitingCounts>({})
  const [departments, setDepartments] = useState<Department[]>([])

  const refresh = useCallback(async () => {
    try {
      const res = await fetchNowServing(deptId ?? undefined)
      setCalled(res.now_serving)
      setCounts(res.waiting_counts)
    } catch {
      /* keep last known board on transient failure */
    }
  }, [deptId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    // /departments may require a kiosk key in prod; fall back to ids/names from the board.
    listDepartments()
      .then(setDepartments)
      .catch(() => setDepartments([]))
  }, [])

  const connected = useReconnectingSocket(
    wsUrl('/ws/display'),
    (msg) => {
      if (!isDisplayMessage(msg)) return
      if (msg.type === 'token.called') {
        const t = msg.data
        if (deptId && t.dept_id !== deptId) return
        setCalled((prev) => [t, ...prev.filter((p) => p.token !== t.token)].slice(0, MAX_RECENT))
        announceToken(t.token, t.room)
      } else {
        const next = deptId ? { [deptId]: msg.data[deptId] ?? 0 } : msg.data
        setCounts(next)
      }
    },
    () => void refresh(),
  )

  useEffect(() => {
    if (connected) return
    const id = window.setInterval(() => void refresh(), 15000)
    return () => window.clearInterval(id)
  }, [connected, refresh])

  return { called, counts, departments, connected }
}
