/**
 * Kiosk text-to-speech. Asks the backend once (`GET /tts/config`) which provider
 * is active. With "sarvam", audio comes from `POST /tts` (WAV) and plays through
 * an Audio element; on any failure (or provider "browser") it falls back to the
 * browser's speechSynthesis. New speak() calls cancel previous playback.
 */

export type TtsLang = 'en' | 'ta';

const BASE_URL: string = import.meta.env.VITE_API_URL ?? '';
const KIOSK_KEY: string | undefined = import.meta.env.VITE_KIOSK_KEY;

let providerPromise: Promise<'browser' | 'sarvam'> | null = null;
let currentAudio: HTMLAudioElement | null = null;
let currentUrl: string | null = null;
let currentAbort: AbortController | null = null;
let currentResolve: (() => void) | null = null;
let generation = 0;
const listeners = new Set<(speaking: boolean) => void>();
let speakingFlag = false;

function setSpeaking(v: boolean) {
  if (speakingFlag === v) return;
  speakingFlag = v;
  listeners.forEach((l) => l(v));
}

/** True while a Sarvam clip is loading/playing (browser speech is polled separately). */
export function isSarvamSpeaking(): boolean {
  return speakingFlag;
}

export function onSpeakingChange(fn: (speaking: boolean) => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

function getProvider(): Promise<'browser' | 'sarvam'> {
  if (!providerPromise) {
    providerPromise = fetch(`${BASE_URL}/tts/config`)
      .then((r) => (r.ok ? r.json() : { provider: 'browser' }))
      .then((j) => (j.provider === 'sarvam' ? 'sarvam' : 'browser') as 'browser' | 'sarvam')
      .catch(() => {
        providerPromise = null; // retry next time
        return 'browser' as const;
      });
  }
  return providerPromise;
}

function releaseAudio() {
  if (currentAudio) {
    try { currentAudio.pause(); } catch { /* ignore */ }
    currentAudio.removeAttribute('src');
    currentAudio = null;
  }
  if (currentUrl) {
    URL.revokeObjectURL(currentUrl);
    currentUrl = null;
  }
}

/** Stop any Sarvam audio, in-flight fetch and browser speech. */
export function stopSpeaking(): void {
  generation++;
  currentAbort?.abort();
  currentAbort = null;
  releaseAudio();
  try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
  const r = currentResolve;
  currentResolve = null;
  setSpeaking(false);
  r?.();
}

function speakBrowser(text: string, lang: TtsLang, rate = 0.9): Promise<void> {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) { resolve(); return; }
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang === 'ta' ? 'ta-IN' : 'en-IN';
    u.rate = rate;
    u.pitch = 1;
    u.onend = () => resolve();
    u.onerror = () => resolve();
    window.speechSynthesis.speak(u);
  });
}

async function playSarvam(text: string, lang: TtsLang, gen: number): Promise<boolean> {
  const ctrl = new AbortController();
  currentAbort = ctrl;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (KIOSK_KEY) headers['X-Kiosk-Key'] = KIOSK_KEY;
  const res = await fetch(`${BASE_URL}/tts`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ text: text.slice(0, 500), language: lang }),
    signal: ctrl.signal,
  });
  if (!res.ok) throw new Error(`tts ${res.status}`);
  const blob = await res.blob();
  if (gen !== generation) return true; // superseded; nothing to play
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  currentAudio = audio;
  currentUrl = url;
  await new Promise<void>((resolve, reject) => {
    currentResolve = resolve;
    audio.onended = () => resolve();
    audio.onerror = () => reject(new Error('audio error'));
    audio.play().catch(reject);
  });
  if (gen === generation) { currentResolve = null; releaseAudio(); }
  return true;
}

/**
 * Speak text. Resolves when playback ends (or is cancelled). Never rejects.
 * Cancels whatever was playing before.
 */
export async function speak(text: string, lang: TtsLang): Promise<void> {
  if (!text.trim()) return;
  stopSpeaking();
  return run(text, lang);
}

async function run(text: string, lang: TtsLang): Promise<void> {
  const gen = generation;
  setSpeaking(true);
  try {
    if ((await getProvider()) === 'sarvam' && gen === generation) {
      try {
        await playSarvam(text, lang, gen);
        return;
      } catch (e) {
        if (gen !== generation) return; // cancelled, not a failure
        console.warn('[TTS] Sarvam failed, using browser voice:', e);
        releaseAudio();
      }
    }
    if (gen !== generation) return;
    await speakBrowser(text, lang);
  } finally {
    if (gen === generation) setSpeaking(false);
  }
}

/** Speak Tamil then English back to back (browser or Sarvam). */
export async function speakBoth(en: string, ta: string): Promise<void> {
  stopSpeaking();
  const g = generation;
  await run(ta, 'ta');
  if (g !== generation) return;
  await run(en, 'en');
}
