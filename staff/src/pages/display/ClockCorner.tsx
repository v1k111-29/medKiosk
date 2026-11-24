import { useNow } from '../../hooks/useNow'

export default function ClockCorner() {
  const now = new Date(useNow(1000))
  return (
    <div className="text-right leading-tight">
      <div className="font-mono text-5xl font-bold tabular-nums">
        {now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })}
      </div>
      <div className="text-xl text-slate-300">
        {now.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short', year: 'numeric' })}
      </div>
    </div>
  )
}
