import type { CalledToken } from '../../api/types'

export default function RecentCalls({ items }: { items: CalledToken[] }) {
  return (
    <section className="w-[34%] rounded-3xl bg-slate-800 p-6">
      <h2 className="mb-4 text-3xl font-bold text-slate-200">
        Recently Called / சமீபத்தில் அழைக்கப்பட்டது
      </h2>
      <ul className="space-y-3">
        {items.slice(0, 6).map((t) => (
          <li
            key={`${t.token}-${t.called_at}`}
            className="flex items-center justify-between rounded-2xl bg-slate-700 px-5 py-3"
          >
            <span className="text-5xl font-extrabold text-white">{t.token}</span>
            <span className="text-4xl font-bold text-yellow-300">{t.room}</span>
          </li>
        ))}
        {items.length === 0 && <li className="text-2xl text-slate-400">-</li>}
      </ul>
    </section>
  )
}
