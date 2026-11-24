import clsx from 'clsx'
import type { Urgency } from '../../api/types'

const STYLES: Record<Urgency, string> = {
  emergency: 'bg-red-600 text-white',
  urgent: 'bg-amber-400 text-amber-950',
  normal: 'bg-gray-200 text-gray-700',
}

export default function UrgencyBadge({ urgency }: { urgency: Urgency }) {
  return (
    <span className={clsx('rounded-full px-2.5 py-0.5 text-xs font-bold uppercase', STYLES[urgency])}>
      {urgency}
    </span>
  )
}
