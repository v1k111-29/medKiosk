import { AlertTriangle, Clock } from 'lucide-react'
import clsx from 'clsx'
import type { QueueAction, QueueItem } from '../../api/types'
import { formatElapsed } from '../../lib/format'
import RowActions from './RowActions'
import EscalationTags from './EscalationTags'
import News2Badge from './News2Badge'
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
        'flex flex-wrap items-center gap-4 rounded-xl border-l-8 p-4 shadow-sm',
        item.urgency === 'emergency' && 'border-red-600 bg-red-50 ring-2 ring-red-500',
        item.urgency === 'urgent' && 'border-amber-400 bg-white',
        item.urgency === 'normal' && 'border-gray-200 bg-white',
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
          {item.urgency === 'emergency' && <AlertTriangle className="h-5 w-5 text-red-600" />}
          <UrgencyBadge urgency={item.urgency} />
          <News2Badge news2={item.vitals?.news2 ?? null} />
          <span className="rounded bg-secondary px-2 py-0.5 text-xs text-gray-600">{item.dept_name}</span>
        </div>
        <div className="text-xs text-gray-500">{meta}</div>
        {item.symptoms && <div className="line-clamp-2 text-sm text-gray-700">{item.symptoms}</div>}
        <VitalsChips vitals={item.vitals} />
        <EscalationTags reasons={item.escalation_reasons} />
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
