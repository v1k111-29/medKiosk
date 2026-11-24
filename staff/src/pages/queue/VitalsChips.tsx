import clsx from 'clsx'
import type { QueueVitals } from '../../api/types'

function Chip({ label, value, alert }: { label: string; value: string; alert: boolean }) {
  return (
    <span
      className={clsx(
        'rounded-md px-2 py-0.5 text-xs font-medium',
        alert ? 'bg-red-100 text-red-800 ring-1 ring-red-300' : 'bg-gray-100 text-gray-700',
      )}
    >
      {label} <b>{value}</b>
    </span>
  )
}

export default function VitalsChips({ vitals }: { vitals: QueueVitals | null }) {
  if (!vitals) return <span className="text-xs text-gray-400">No vitals</span>
  const flagged = vitals.flags.length > 0
  const chips: Array<{ label: string; value: string }> = []
  if (vitals.bp_sys != null && vitals.bp_dia != null)
    chips.push({ label: 'BP', value: `${vitals.bp_sys}/${vitals.bp_dia}` })
  if (vitals.spo2 != null) chips.push({ label: 'SpO2', value: `${vitals.spo2}%` })
  if (vitals.pulse != null) chips.push({ label: 'HR', value: String(vitals.pulse) })
  if (vitals.temperature != null) chips.push({ label: 'Temp', value: `${vitals.temperature}°C` })
  if (vitals.glucose != null) chips.push({ label: 'Glu', value: String(vitals.glucose) })

  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((c) => (
        <Chip key={c.label} label={c.label} value={c.value} alert={false} />
      ))}
      {vitals.flags.map((f) => (
        <span key={f} className="rounded-md bg-red-600 px-2 py-0.5 text-xs font-semibold text-white">
          {f}
        </span>
      ))}
      {chips.length === 0 && !flagged && <span className="text-xs text-gray-400">No vitals</span>}
    </div>
  )
}
