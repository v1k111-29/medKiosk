import { useEffect, useState } from 'react'
import { Loader2, PhoneForwarded } from 'lucide-react'
import { errorMessage } from '../../api/client'
import { listDepartments } from '../../api/departments'
import { callNext, queueAction } from '../../api/queue'
import type { Department, QueueAction, QueueItem, QueueStatus } from '../../api/types'
import ConnectionBadge from '../../components/ConnectionBadge'
import { useNow } from '../../hooks/useNow'
import QueueRow from './QueueRow'
import StatusTabs from './StatusTabs'
import { useQueue } from './useQueue'

export default function QueuePage() {
  const [departments, setDepartments] = useState<Department[]>([])
  const [deptId, setDeptId] = useState('')
  const [tab, setTab] = useState<QueueStatus>('waiting')
  const [busyId, setBusyId] = useState<number | null>(null)
  const [callingNext, setCallingNext] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const now = useNow(1000)
  const { items, counts, connected, loading, error, refresh, upsert } = useQueue(deptId)

  useEffect(() => {
    listDepartments()
      .then(setDepartments)
      .catch((err: unknown) => setActionError(errorMessage(err)))
  }, [])

  const visible = items.filter((i) => i.status === tab)

  const onAction = async (item: QueueItem, action: QueueAction) => {
    setBusyId(item.appointment_id)
    setActionError(null)
    try {
      upsert(await queueAction(item.appointment_id, action))
    } catch (err) {
      setActionError(errorMessage(err))
      void refresh()
    } finally {
      setBusyId(null)
    }
  }

  const onCallNext = async () => {
    if (!deptId) return
    setCallingNext(true)
    setActionError(null)
    try {
      await callNext(deptId)
      await refresh()
      setTab('called')
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setCallingNext(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={deptId}
          onChange={(e) => setDeptId(e.target.value)}
          className="rounded-lg border bg-white px-3 py-2 text-sm font-medium"
          aria-label="Department"
        >
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name_en} ({d.room})
            </option>
          ))}
        </select>
        <button
          onClick={onCallNext}
          disabled={!deptId || callingNext}
          title={deptId ? 'Call highest-priority waiting patient' : 'Select a department first'}
          className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-white disabled:opacity-40"
        >
          {callingNext ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneForwarded className="h-4 w-4" />}
          Call next
        </button>
        <div className="ml-auto">
          <ConnectionBadge connected={connected} />
        </div>
      </div>

      <StatusTabs active={tab} counts={counts} onChange={setTab} />

      {(error || actionError) && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError ?? error}</p>
      )}

      {loading ? (
        <div className="flex justify-center py-16 text-gray-400">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : visible.length === 0 ? (
        <p className="py-16 text-center text-gray-400">No patients in this list.</p>
      ) : (
        <ul className="space-y-3">
          {visible.map((item) => (
            <QueueRow
              key={item.appointment_id}
              item={item}
              now={now}
              busy={busyId === item.appointment_id}
              onAction={onAction}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
