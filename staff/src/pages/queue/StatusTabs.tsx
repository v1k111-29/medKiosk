import clsx from 'clsx'
import type { QueueCounts, QueueStatus } from '../../api/types'

export const STATUS_TABS: Array<{ id: QueueStatus; label: string }> = [
  { id: 'waiting', label: 'Waiting' },
  { id: 'called', label: 'Called' },
  { id: 'in_consult', label: 'In consult' },
  { id: 'done', label: 'Done' },
  { id: 'no_show', label: 'No-show' },
]

interface Props {
  active: QueueStatus
  counts: QueueCounts
  onChange: (s: QueueStatus) => void
}

export default function StatusTabs({ active, counts, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {STATUS_TABS.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={clsx(
            'rounded-lg px-4 py-2 text-sm font-semibold transition',
            active === t.id ? 'bg-primary text-white' : 'bg-white text-dark hover:bg-gray-100',
          )}
        >
          {t.label}
          <span
            className={clsx(
              'ml-2 rounded-full px-2 py-0.5 text-xs',
              active === t.id ? 'bg-white/25' : 'bg-gray-200',
            )}
          >
            {counts[t.id]}
          </span>
        </button>
      ))}
    </div>
  )
}
