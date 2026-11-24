import clsx from 'clsx'
import { Bell, CheckCircle2, PlayCircle, RotateCcw, UserX } from 'lucide-react'
import type { ReactNode } from 'react'
import type { QueueAction, QueueStatus } from '../../api/types'

interface ActionDef {
  action: QueueAction
  label: string
  icon: ReactNode
  style: string
}

const CALL = (label: string): ActionDef => ({
  action: 'call',
  label,
  icon: <Bell className="h-4 w-4" />,
  style: 'bg-primary text-white',
})
const START: ActionDef = {
  action: 'start',
  label: 'Start',
  icon: <PlayCircle className="h-4 w-4" />,
  style: 'bg-blue-600 text-white',
}
const COMPLETE: ActionDef = {
  action: 'complete',
  label: 'Complete',
  icon: <CheckCircle2 className="h-4 w-4" />,
  style: 'bg-emerald-600 text-white',
}
const NO_SHOW: ActionDef = {
  action: 'no-show',
  label: 'No-show',
  icon: <UserX className="h-4 w-4" />,
  style: 'bg-white text-red-700 ring-1 ring-red-300',
}
const REQUEUE: ActionDef = {
  action: 'requeue',
  label: 'Requeue',
  icon: <RotateCcw className="h-4 w-4" />,
  style: 'bg-white text-dark ring-1 ring-gray-300',
}

const BY_STATUS: Record<QueueStatus, ActionDef[]> = {
  waiting: [CALL('Call'), NO_SHOW],
  called: [CALL('Recall'), START, NO_SHOW, REQUEUE],
  in_consult: [COMPLETE],
  done: [],
  no_show: [REQUEUE],
}

interface Props {
  status: QueueStatus
  busy: boolean
  onAction: (a: QueueAction) => void
}

export default function RowActions({ status, busy, onAction }: Props) {
  return (
    <div className="flex flex-wrap justify-end gap-2">
      {BY_STATUS[status].map((d) => (
        <button
          key={d.label}
          disabled={busy}
          onClick={() => onAction(d.action)}
          className={clsx(
            'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold disabled:opacity-50',
            d.style,
          )}
        >
          {d.icon} {d.label}
        </button>
      ))}
    </div>
  )
}
