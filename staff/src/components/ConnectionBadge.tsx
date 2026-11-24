import { Wifi, WifiOff } from 'lucide-react'
import clsx from 'clsx'

export default function ConnectionBadge({ connected }: { connected: boolean }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold',
        connected ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800',
      )}
      title={connected ? 'Receiving live updates' : 'Disconnected - refreshing every 15s'}
    >
      {connected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
      {connected ? 'Live' : 'Offline - polling'}
    </span>
  )
}
