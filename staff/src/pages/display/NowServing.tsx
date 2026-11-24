import type { CalledToken } from '../../api/types'

export default function NowServing({ current }: { current: CalledToken | undefined }) {
  return (
    <section className="flex flex-1 flex-col items-center justify-center rounded-3xl bg-emerald-900 p-8 text-center">
      <h2 className="text-4xl font-bold text-emerald-200">
        Now Serving <span className="mx-2 text-emerald-400">/</span> இப்போது அழைக்கப்படுகிறது
      </h2>
      {current ? (
        <>
          <div className="my-6 text-[14rem] font-black leading-none tracking-wider text-white">
            {current.token}
          </div>
          <div className="text-6xl font-bold text-yellow-300">
            Room / அறை: {current.room}
          </div>
          <div className="mt-4 text-3xl text-emerald-100">{current.dept_name}</div>
        </>
      ) : (
        <div className="my-16 text-6xl font-bold text-emerald-300">
          Please wait / காத்திருக்கவும்
        </div>
      )}
    </section>
  )
}
