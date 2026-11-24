import type { Department, WaitingCounts } from '../../api/types'

interface Props {
  counts: WaitingCounts
  departments: Department[]
  names: Record<string, string>
}

export default function WaitingStrip({ counts, departments, names }: Props) {
  const ids = departments.length > 0 ? departments.map((d) => d.id) : Object.keys(counts)
  const byId = new Map(departments.map((d) => [d.id, d]))

  return (
    <section className="rounded-3xl bg-slate-800 p-5">
      <h2 className="mb-3 text-2xl font-bold text-slate-200">
        Waiting / காத்திருப்போர்
      </h2>
      <div className="flex flex-wrap gap-3">
        {ids.map((id) => {
          const d = byId.get(id)
          return (
            <div key={id} className="min-w-[200px] flex-1 rounded-2xl bg-slate-700 px-4 py-3">
              <div className="text-xl font-semibold text-slate-100">{d?.name_en ?? names[id] ?? id}</div>
              {d && <div className="text-lg text-slate-300">{d.name_ta}</div>}
              <div className="text-5xl font-black text-yellow-300">{counts[id] ?? 0}</div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
