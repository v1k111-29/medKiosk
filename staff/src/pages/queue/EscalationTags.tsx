// Backend reason strings (app/services/clinical_rules.py, app/routers/appointment.py):
//   "Red flag (emergency): Chest pain [nenju vali]"
//   "NEWS2 6 (medium, partial) -> urgent"
//   "Kiosk triage: emergency" / "<llm label>: <urgency>"
//   "Routed to Emergency (requested cardio)"
// Show a short label; keep the full text in the tooltip.
function shortLabel(reason: string): string {
  let m = reason.match(/^Red flag \(\w+\): (.+?) \[.*\]$/)
  if (m) return `Red flag: ${m[1]}`
  m = reason.match(/^NEWS2 (\d+) \(([\w-]+)/)
  if (m) return `NEWS2 ${m[1]} · ${m[2]}`
  m = reason.match(/^Routed to Emergency/)
  if (m) return 'Moved to Emergency'
  m = reason.match(/^(.+?) triage: (\w+)$/)
  if (m) return `${m[1]}: ${m[2]}`
  return reason
}

export default function EscalationTags({ reasons }: { reasons: string[] | undefined }) {
  if (!reasons || reasons.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {reasons.map((r) => (
        <span
          key={r}
          title={r}
          className="rounded bg-red-50 px-1.5 py-0.5 text-[11px] font-medium text-red-700 ring-1 ring-red-200"
        >
          {shortLabel(r)}
        </span>
      ))}
    </div>
  )
}
