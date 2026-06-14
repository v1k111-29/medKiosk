import { useRef, useState, useCallback } from 'react';
import { useKioskStore } from '../store/useKioskStore';

// ── TTS ────────────────────────────────────────────────────────────────────
export function useTTS() {
  const { language } = useKioskStore();

  const speak = useCallback((text: string, lang?: 'en' | 'ta') => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = (lang ?? language) === 'ta' ? 'ta-IN' : 'en-IN';
    utter.rate = 0.9;
    utter.pitch = 1;
    window.speechSynthesis.speak(utter);
  }, [language]);

  const speakBoth = useCallback((en: string, ta: string) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const u1 = new SpeechSynthesisUtterance(ta);
    u1.lang = 'ta-IN'; u1.rate = 0.88;
    const u2 = new SpeechSynthesisUtterance(en);
    u2.lang = 'en-IN'; u2.rate = 0.9;
    window.speechSynthesis.speak(u1);
    window.speechSynthesis.speak(u2);
  }, []);

  const cancel = useCallback(() => {
    window.speechSynthesis.cancel();
  }, []);

  return { speak, speakBoth, cancel };
}

// ── STT (Web Speech API — no backend needed) ───────────────────────────────
interface STTOptions {
  onResult: (text: string) => void;
  onEnd?: () => void;
  lang?: string;
}

export function useSTT() {
  const [isListening, setIsListening] = useState(false);
  const recognizerRef = useRef<any>(null);
  const { language } = useKioskStore();

  const startListening = useCallback(({ onResult, onEnd, lang }: STTOptions) => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      console.warn('SpeechRecognition not supported');
      return;
    }
    const rec = new SR();
    recognizerRef.current = rec;
    rec.lang = lang ?? (language === 'ta' ? 'ta-IN' : 'en-IN');
    rec.interimResults = false;
    rec.maxAlternatives = 1;
    rec.continuous = false;

    rec.onresult = (e: any) => {
      const transcript = e.results[0][0].transcript;
      onResult(transcript);
    };

    rec.onend = () => {
      setIsListening(false);
      onEnd?.();
    };
    rec.onerror = () => {
      setIsListening(false);
    };

    rec.start();
    setIsListening(true);
  }, [language]);

  const stopListening = useCallback(() => {
    recognizerRef.current?.stop();
    setIsListening(false);
  }, []);

  return { startListening, stopListening, isListening };
}

// ── Combined voice-field hook ──────────────────────────────────────────────
// Used by Registration and Triage to show mic button per field
export function useVoiceField() {
  const [activeField, setActiveField] = useState<string | null>(null);
  const { startListening, stopListening, isListening } = useSTT();
  const { speak } = useTTS();
  const { language } = useKioskStore();

  const listenFor = useCallback((
    fieldKey: string,
    prompt: { en: string; ta: string },
    onValue: (v: string) => void,
    transform?: (raw: string) => string
  ) => {
    speak(language === 'ta' ? prompt.ta : prompt.en);
    setActiveField(fieldKey);
    setTimeout(() => {
      startListening({
        onResult: (text) => {
          const val = transform ? transform(text) : text;
          onValue(val);
          setActiveField(null);
        },
        onEnd: () => setActiveField(null),
        lang: language === 'ta' ? 'ta-IN' : 'en-IN',
      });
    }, 1400); // wait for TTS to finish speaking
  }, [language, speak, startListening]);

  return { listenFor, activeField, isListening };
}
