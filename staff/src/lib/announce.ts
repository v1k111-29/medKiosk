let ctx: AudioContext | null = null

interface WindowWithWebkitAudio {
  webkitAudioContext?: typeof AudioContext
}

function audio(): AudioContext | null {
  try {
    if (!ctx) {
      const Ctor = window.AudioContext ?? (window as unknown as WindowWithWebkitAudio).webkitAudioContext
      if (!Ctor) return null
      ctx = new Ctor()
    }
    return ctx
  } catch {
    return null
  }
}

/** Call from a user gesture so browsers allow later automatic playback. */
export function unlockAudio(): void {
  const c = audio()
  if (c && c.state === 'suspended') void c.resume()
  if ('speechSynthesis' in window) {
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(''))
  }
}

/** Two-note chime (WebAudio, no assets). */
export function playChime(): Promise<void> {
  const c = audio()
  if (!c) return Promise.resolve()
  if (c.state === 'suspended') void c.resume()
  const notes: Array<[number, number]> = [
    [880, 0],
    [660, 0.35],
  ]
  const t0 = c.currentTime
  for (const [freq, offset] of notes) {
    const osc = c.createOscillator()
    const gain = c.createGain()
    osc.type = 'sine'
    osc.frequency.value = freq
    gain.gain.setValueAtTime(0.0001, t0 + offset)
    gain.gain.exponentialRampToValueAtTime(0.4, t0 + offset + 0.03)
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + offset + 0.6)
    osc.connect(gain).connect(c.destination)
    osc.start(t0 + offset)
    osc.stop(t0 + offset + 0.65)
  }
  return new Promise((resolve) => window.setTimeout(resolve, 900))
}

function speak(text: string, lang: string): Promise<void> {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) {
      resolve()
      return
    }
    const u = new SpeechSynthesisUtterance(text)
    u.lang = lang
    const prefix = lang.slice(0, 2).toLowerCase()
    const voice = window.speechSynthesis
      .getVoices()
      .find((v) => v.lang.toLowerCase().startsWith(prefix))
    if (voice) u.voice = voice
    u.rate = 0.9
    u.onend = () => resolve()
    u.onerror = () => resolve()
    window.speechSynthesis.speak(u)
  })
}

/** "C-004" -> "C 0 0 4" so it is read character by character. */
function spellToken(token: string): string {
  return token
    .replace(/-/g, '')
    .split('')
    .join(' ')
}

let chain: Promise<void> = Promise.resolve()

/** Queue an announcement: chime, English, then Tamil. Announcements never overlap. */
export function announceToken(token: string, room: string): void {
  chain = chain.then(async () => {
    const spelled = spellToken(token)
    await playChime()
    await speak(`Token ${spelled}, please go to room ${room}`, 'en-IN')
    await speak(`டோக்கன் ${spelled}, அறை ${room} க்குச் செல்லவும்`, 'ta-IN')
  })
}
