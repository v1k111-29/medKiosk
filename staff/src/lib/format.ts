/** Parse an API timestamp; naive ISO strings (no zone) are treated as UTC. */
export function parseApiTime(iso: string): number {
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(iso)
  return new Date(hasZone ? iso : `${iso}Z`).getTime()
}

/** Elapsed time as m:ss or h:mm:ss. */
export function formatElapsed(fromIso: string, now: number): string {
  const total = Math.max(0, Math.floor((now - parseApiTime(fromIso)) / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

export function tokenNumber(token: string): number {
  const m = /(\d+)$/.exec(token)
  return m ? parseInt(m[1], 10) : 0
}
