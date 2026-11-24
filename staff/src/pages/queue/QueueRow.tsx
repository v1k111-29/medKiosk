import { Clock } from 'lucide-react'
import clsx from 'clsx'
import type { QueueAction, QueueItem } from '../../api/types'
import { formatElapsed } from '../../lib/format'
import RowActions from './RowActions'
import UrgencyBadge from './UrgencyBadge'
import VitalsChips from './VitalsChips'

interface Props {
  item: QueueItem
  now: number
  busy: boolean
  onAction: (item: QueueItem, a: QueueAction) => void
}

export default function QueueRow({ item, now, busy, onAction }: Props) {
  const { patient } = item
  const meta = [patient.age != null ? `${patient.age}y` : null, patient.gender, patient.phone_masked]
    .filter(Boolean)
    .join(' · ')
  const active = item.status === 'waiting' || item.status === 'called'

  return (
    <li
      className={clsx(
        'flex flex-wrap items-center gap-4 rounded-xl border-l-4 bg-white p-4 shadow-sm',
        item.urgency === 'emergency'
          ? 'border-red-600'
          : item.urgency === 'urgent'
            ? 'border-amber-400'
            : 'border-gray-200',
      )}
    >
      <div className="w-24 shrink-0">
        <div className="text-2xl font-extrabold text-dark">{item.token}</div>
        <div className="text-xs text-gray-500">
          {item.room}
        </div>
      </div>

      <div className="min-w-[200px] flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-dark">{patient.name}</span>
          <UrgencyBadge urgency={item.urgency} />
          <span className="rounded bg-secondary px-2 py-0.5 text-xs text-gray-600">{item.dept_name}</span>
        </div>
        <div className="text-xs text-gray-500">{meta}</div>
        {item.symptoms && <div className="line-clamp-2 text-sm text-gray-700">{item.symptoms}</div>}
        <VitalsChips vitals={item.vitals} />
      </div>

      <div
        className="flex w-24 shrink-0 items-center gap-1 font-mono text-sm text-gray-600"
        title="Time since check-in"
      >
        <Clock className="h-4 w-4" />
        {active ? formatElapsed(item.created_at, now) : '--'}
      </div>

      <div className="ml-auto">
        <RowActions status={item.status} busy={busy} onAction={(a) => onAction(item, a)} />
      </div>
    </li>
  )
}
