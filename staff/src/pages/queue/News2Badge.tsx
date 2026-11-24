import clsx from 'clsx'
import type { News2, News2Band } from '../../api/types'

const STYLES: Record<News2Band, string> = {
  low: 'bg-gray-100 text-gray-700',
  'low-medium': 'bg-amber-100 text-amber-900 ring-1 ring-amber-300',
  medium: 'bg-orange-500 text-white',
  high: 'bg-red-600 text-white',
}

export function news2Tooltip(n: News2): string {
  const lines = Object.entries(n.points).map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
  lines.push(`score ${n.score} (${n.band})`)
  if (n.partial) lines.push('partial — consciousness/O2 not recorded')
  return lines.join('\n')
}

export default function News2Badge({ news2 }: { news2: News2 | null }) {
  if (!news2) return null
  return (
    <span
      title={news2Tooltip(news2)}
      className={clsx('rounded-md px-2 py-0.5 text-xs font-bold', STYLES[news2.band])}
    >
      NEWS2 {news2.score}
      {news2.partial ? '*' : ''}
    </span>
  )
}
