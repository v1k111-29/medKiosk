import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Volume2, WifiOff } from 'lucide-react'
import { unlockAudio } from '../../lib/announce'
import ClockCorner from './ClockCorner'
import NowServing from './NowServing'
import RecentCalls from './RecentCalls'
import WaitingStrip from './WaitingStrip'
import { useDisplay } from './useDisplay'

export default function DisplayPage() {
  const [params] = useSearchParams()
  const dept = params.get('dept')
  const { called, counts, departments, connected } = useDisplay(dept)
  const [soundOn, setSoundOn] = useState(false)

  const visibleDepts = useMemo(
    () => (dept ? departments.filter((d) => d.id === dept) : departments),
    [dept, departments],
  )
  const names = useMemo(() => {
    const out: Record<string, string> = {}
    for (const c of called) out[c.dept_id] = c.dept_name
    return out
  }, [called])

  return (
    <div className="flex h-screen flex-col gap-4 overflow-hidden bg-slate-950 p-6 text-white">
      <header className="flex items-center justify-between">
        <div className="text-4xl font-bold text-slate-100">
          Outpatient Queue <span className="text-slate-400">/ புறநோயாளர் வரிசை</span>
        </div>
        <div className="flex items-center gap-6">
          {!connected && (
            <span className="flex items-center gap-2 rounded-full bg-amber-500 px-4 py-2 text-xl font-bold text-black">
              <WifiOff className="h-6 w-6" /> Reconnecting
            </span>
          )}
          <ClockCorner />
        </div>
      </header>

      <div className="flex min-h-0 flex-1 gap-4">
        <NowServing current={called[0]} />
        <RecentCalls items={called.slice(1)} />
      </div>

      <WaitingStrip counts={counts} departments={visibleDepts} names={names} />

      {!soundOn && (
        <button
          onClick={() => {
            unlockAudio()
            setSoundOn(true)
          }}
          className="fixed bottom-6 right-6 flex items-center gap-3 rounded-full bg-yellow-400 px-6 py-4 text-2xl font-bold text-black shadow-xl"
        >
          <Volume2 className="h-8 w-8" /> Enable sound / ஒலியை இயக்கு
        </button>
      )}
    </div>
  )
}
