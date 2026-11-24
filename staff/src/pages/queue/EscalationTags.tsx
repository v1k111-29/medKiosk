export default function EscalationTags({ reasons }: { reasons: string[] | undefined }) {
  if (!reasons || reasons.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {reasons.map((r) => (
        <span
          key={r}
          className="rounded bg-red-50 px-1.5 py-0.5 text-[11px] font-medium text-red-700 ring-1 ring-red-200"
        >
          {r}
        </span>
      ))}
    </div>
  )
}
