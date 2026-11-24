import { useRef, useState, useCallback, useEffect } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import {
  speak as ttsSpeak,
  speakBoth as ttsSpeakBoth,
  stopSpeaking,
  isSarvamSpeaking,
  onSpeakingChange,
} from '../services/tts';

// ── TTS (Sarvam via backend when configured, else browser speechSynthesis) ──
export function useTTS() {
  const { language } = useKioskStore();
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Sarvam playback state is pushed by the service; browser speech is polled every
  // 200ms because onend is unreliable on Chrome when the queue is cancelled.
  useEffect(() => {
    const unsub = onSpeakingChange(setIsSpeaking);
    const id = setInterval(() => {
      if (isSarvamSpeaking()) return;
      if ('speechSynthesis' in window) setIsSpeaking(window.speechSynthesis.speaking);
    }, 200);
    return () => { unsub(); clearInterval(id); };
  }, []);

  const speak = useCallback((text: string, lang?: 'en' | 'ta') => {
    void ttsSpeak(text, lang ?? language);
  }, [language]);

  const speakBoth = useCallback((en: string, ta: string) => {
    void ttsSpeakBoth(en, ta);
  }, []);

  const cancel = useCallback(() => {
    stopSpeaking();
    setIsSpeaking(false);
  }, []);

  return { speak, speakBoth, cancel, isSpeaking };
}


// ── STT (Web Speech API — no backend needed) ───────────────────────────────
export type STTError =
  | 'not_supported'
  | 'permission_denied'
  | 'no_speech'
  | 'network'
  | 'aborted'
  | 'timeout'
  | 'unknown'
  | null;

interface STTOptions {
  onResult: (text: string) => void;
  onEnd?: () => void;
  onError?: (err: STTError) => void;
  lang?: string;
  /** Max time to wait for a result before giving up (ms). Default 10s. */
  timeoutMs?: number;
}

/**
 * Checks whether the current page is in a "secure context".
 * SpeechRecognition and getUserMedia both silently fail (or throw) on
 * plain http:// pages that aren't localhost — this is the #1 cause of
 * "the mic button does nothing" on a kiosk accessed via LAN IP.
 */
export function isSecureContextOk(): boolean {
  if (typeof window === 'undefined') return true;
  return window.isSecureContext || window.location.hostname === 'localhost';
}

export function isSTTSupported(): boolean {
  if (typeof window === 'undefined') return false;
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  return !!SR;
}

export function useSTT() {
  const [isListening, setIsListening] = useState(false);
  const [lastError, setLastError] = useState<STTError>(null);
  const recognizerRef = useRef<any>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const resultReceivedRef = useRef(false);
  const { language } = useKioskStore();

  const clearTimer = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  const startListening = useCallback(({ onResult, onEnd, onError, lang, timeoutMs = 10000 }: STTOptions) => {
    setLastError(null);
    resultReceivedRef.current = false;

    if (!isSecureContextOk()) {
      console.error('[STT] Insecure context — SpeechRecognition requires HTTPS or localhost');
      setLastError('permission_denied');
      onError?.('permission_denied');
      return;
    }

    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      console.warn('[STT] SpeechRecognition not supported in this browser');
      setLastError('not_supported');
      onError?.('not_supported');
      return;
    }

    // Defensive: if a previous recognizer is still active, stop it first
    if (recognizerRef.current) {
      try { recognizerRef.current.abort(); } catch { /* ignore */ }
      recognizerRef.current = null;
    }

    const rec = new SR();
    recognizerRef.current = rec;
    rec.lang = lang ?? (language === 'ta' ? 'ta-IN' : 'en-IN');
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.continuous = false;

    rec.onresult = (e: any) => {
      resultReceivedRef.current = true;
      clearTimer();
      const transcript = e.results?.[0]?.[0]?.transcript ?? '';
      if (!transcript.trim()) {
        setLastError('no_speech');
        onError?.('no_speech');
        return;
      }
      onResult(transcript);
    };

    rec.onspeechend = () => {
      // Some browsers (notably Chrome on Android) need an explicit stop()
      // once speech ends, or onend never fires.
      try { rec.stop(); } catch { /* already stopped */ }
    };

    rec.onend = () => {
      clearTimer();
      setIsListening(false);
      if (!resultReceivedRef.current && !lastErrorIsTerminal(lastError)) {
        // onend fired with no result and no prior error — treat as "no speech"
        setLastError(prev => prev ?? 'no_speech');
        onError?.('no_speech');
      }
      onEnd?.();
    };

    rec.onerror = (e: any) => {
      clearTimer();
      console.warn('[STT] onerror:', e?.error);
      let mapped: STTError = 'unknown';
      switch (e?.error) {
        case 'not-allowed':
        case 'service-not-allowed':
          mapped = 'permission_denied'; break;
        case 'no-speech':
          mapped = 'no_speech'; break;
        case 'network':
          mapped = 'network'; break;
        case 'aborted':
          mapped = 'aborted'; break;
        default:
          mapped = 'unknown';
      }
      setLastError(mapped);
      setIsListening(false);
      onError?.(mapped);
    };

    try {
      rec.start();
      setIsListening(true);

      // Safety timeout — if neither onresult nor onend fires (happens on
      // some Chrome builds after a network blip), force-stop after timeoutMs.
      timeoutRef.current = setTimeout(() => {
        if (!resultReceivedRef.current) {
          console.warn('[STT] Timed out waiting for result — aborting');
          try { rec.abort(); } catch { /* ignore */ }
          setIsListening(false);
          setLastError('timeout');
          onError?.('timeout');
        }
      }, timeoutMs);
    } catch (err) {
      console.error('[STT] start() threw:', err);
      setIsListening(false);
      setLastError('unknown');
      onError?.('unknown');
    }
  }, [language, lastError]);

  const stopListening = useCallback(() => {
    clearTimer();
    try { recognizerRef.current?.stop(); } catch { /* ignore */ }
    setIsListening(false);
  }, []);

  return { startListening, stopListening, isListening, lastError };
}

function lastErrorIsTerminal(err: STTError) {
  return err !== null;
}

// ── Combined voice-field hook ──────────────────────────────────────────────
// Used by Registration and Vitals to show a mic button per field
export function useVoiceField() {
  const [activeField, setActiveField] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<STTError>(null);
  const { startListening, stopListening, isListening } = useSTT();
  const { speak } = useTTS();
  const { language } = useKioskStore();

  const listenFor = useCallback((
    fieldKey: string,
    prompt: { en: string; ta: string },
    onValue: (v: string) => void,
    transform?: (raw: string) => string
  ) => {
    setFieldError(null);

    if (!isSTTSupported()) {
      setFieldError('not_supported');
      return;
    }

    speak(language === 'ta' ? prompt.ta : prompt.en);
    setActiveField(fieldKey);

    // Wait for the prompt to finish speaking before listening, so the
    // mic doesn't pick up the kiosk's own TTS output.
    const estMs = Math.min(2500, Math.max(1200, (language === 'ta' ? prompt.ta : prompt.en).length * 55));

    setTimeout(() => {
      startListening({
        lang: language === 'ta' ? 'ta-IN' : 'en-IN',
        onResult: (text) => {
          const val = transform ? transform(text) : text;
          onValue(val);
          setActiveField(null);
        },
        onEnd: () => setActiveField(null),
        onError: (err) => {
          setFieldError(err);
          setActiveField(null);
        },
      });
    }, estMs);
  }, [language, speak, startListening]);

  const cancel = useCallback(() => {
    stopListening();
    setActiveField(null);
  }, [stopListening]);

  return { listenFor, activeField, isListening, fieldError, cancel };
}
