/**
 * useConversationalRegistration
 *
 * Drives the full voice-based registration flow:
 *   1. Start recording (Whisper via /transcribe)
 *   2. Send transcript + current fields to /conversation/register (Ollama)
 *   3. Ollama extracts new fields, returns a natural-language reply
 *   4. TTS speaks the reply
 *   5. Auto-fill extracted fields into the form
 *   6. Repeat until all_collected === true or user submits manually
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { faceApi } from '../services/api';
import { useTTS } from './useVoice';
import { useVAD } from './useVAD';

export interface CollectedFields {
  name: string | null;
  age: string | null;
  phone: string | null;
  blood_group: string | null;
  city: string | null;
}

export interface ConvMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface UseConvRegOptions {
  language?: 'en' | 'ta' | 'auto';
  onFieldsExtracted?: (fields: Partial<CollectedFields>) => void;
  onAllCollected?: () => void;
}

function pickMimeType(): string {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/ogg',
  ];
  for (const m of candidates) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return '';
}

/**
 * RMS energy check: decode the audio blob and measure signal level.
 * Returns false (= skip transcription) when the audio is too quiet to contain
 * real speech — i.e. it’s just ambient hiss, AC noise, or a mic click.
 *
 * Real speech RMS is typically 0.02–0.15.
 * Ambient noise / silence RMS is typically 0.001–0.007.
 * Threshold 0.008 sits between these ranges with a small safety margin.
 */
async function checkAudioHasVoice(_blob: Blob): Promise<boolean> {
  // ⚡ TEMPORARILY DISABLED — always pass audio to Whisper.
  // Re-enable by restoring the RMS energy check below.
  // To re-enable: remove this return and uncomment the original body.
  return true;
  /* --- original RMS filter (disabled) ---
  try {
    const arrayBuffer = await _blob.arrayBuffer();
    const ctx = new OfflineAudioContext(1, 1, 44100);
    const decoded = await ctx.decodeAudioData(arrayBuffer);
    const data = decoded.getChannelData(0);
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    const rms = Math.sqrt(sum / data.length);
    console.debug(`[ConvReg] Audio RMS energy: ${rms.toFixed(5)}`);
    return rms > 0.008;
  } catch {
    return true;
  }
  --- end original --- */
}

export function useConversationalRegistration(options: UseConvRegOptions = {}) {
  const { language = 'en', onFieldsExtracted, onAllCollected } = options;
  const { speak, isSpeaking } = useTTS();

  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [history, setHistory] = useState<ConvMessage[]>([]);
  const [collectedFields, setCollectedFields] = useState<CollectedFields>({
    name: null, age: null, phone: null, blood_group: null, city: null,
  });
  const [allCollected, setAllCollected] = useState(false);
  const [lastReply, setLastReply] = useState('');
  const [error, setError] = useState<string | null>(null);

  // VAD stream state
  const [micStream, setMicStream] = useState<MediaStream | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const isProcessingRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // historyRef always tracks the latest history to avoid stale closures in sendToLLM
  const historyRef = useRef<ConvMessage[]>([]);
  // Keep ref in sync with state
  useEffect(() => {
    historyRef.current = history;
  }, [history]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      micStream?.getTracks().forEach(t => t.stop());
      abortControllerRef.current?.abort();
    };
  }, [micStream]);

  // Initialize persistent microphone stream for VAD
  const initListening = useCallback(async () => {
    if (micStream || isProcessingRef.current) return;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Microphone not available. Please use HTTPS or localhost.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setMicStream(stream);
    } catch (err: any) {
      const msg = err?.name === 'NotAllowedError'
        ? "Microphone permission denied. Please allow access."
        : "Could not access microphone.";
      setError(msg);
      speak(msg, 'en');
    }
  }, [micStream, speak]);

  const sendToLLM = useCallback(async (transcript: string) => {
    if (isProcessingRef.current) return;
    isProcessingRef.current = true;
    setIsProcessing(true);
    setError(null);

    const userMsg: ConvMessage = { role: 'user', content: transcript };
    const updatedHistory = [...historyRef.current, userMsg];
    setHistory(updatedHistory);

    try {
      abortControllerRef.current = new AbortController();
      const res = await faceApi.post(
        '/conversation/register',
        {
          text: transcript,
          collected_fields: collectedFields,
          history: updatedHistory,
        },
        { signal: abortControllerRef.current.signal, timeout: 30000 }
      );

      const data = res.data;
      const reply: string = data.reply || "Could you please repeat that?";
      const extracted: Partial<CollectedFields> = data.extracted || {};
      const isAllCollected: boolean = data.all_collected === true;

      if (Object.keys(extracted).length > 0) {
        setCollectedFields(prev => {
          const merged = { ...prev };
          for (const key of Object.keys(extracted) as (keyof CollectedFields)[]) {
            const val = extracted[key];
            if (val !== null && val !== undefined && val !== '') {
              merged[key] = String(val);
            }
          }
          return merged;
        });
        onFieldsExtracted?.(extracted);
      }

      const assistantMsg: ConvMessage = { role: 'assistant', content: reply };
      setHistory([...updatedHistory, assistantMsg]);
      setLastReply(reply);

      // Tell TTS to speak; VAD will automatically pause during this
      speak(reply, 'en');

      if (isAllCollected) {
        setAllCollected(true);
        onAllCollected?.();
      }
    } catch (err: any) {
      if (err?.name === 'CanceledError' || err?.name === 'AbortError') return;
      console.error('[ConvReg] LLM call failed:', err);
      const errMsg = "I'm having a little trouble. Could you please say that again?";
      setError(errMsg);
      setLastReply(errMsg);
      speak(errMsg, 'en');
      setHistory(h => [...h, { role: 'assistant', content: errMsg }]);
    } finally {
      isProcessingRef.current = false;
      setIsProcessing(false);
    }
  }, [collectedFields, speak, onFieldsExtracted, onAllCollected]);

  // VAD Callback: Speech detected, start recording
  const handleSpeechStart = useCallback(() => {
    if (!micStream || isRecording || isProcessingRef.current) return;
    try {
      const mimeType = pickMimeType();
      mediaRecorderRef.current = mimeType
        ? new MediaRecorder(micStream, { mimeType })
        : new MediaRecorder(micStream);
      chunksRef.current = [];
      startTimeRef.current = Date.now();

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const duration = Date.now() - startTimeRef.current;
        const usedMime = mediaRecorderRef.current?.mimeType || mimeType || 'audio/webm';
        const audioBlob = new Blob(chunksRef.current, { type: usedMime });

        if (duration < 1000 || audioBlob.size < 3000) {
          // Too short, just ignore silently instead of erroring during VAD
          return;
        }

        // RMS energy guard: skip transcription if the audio is just ambient
        // noise / silence — no point sending it to Groq Whisper.
        const hasVoice = await checkAudioHasVoice(audioBlob);
        if (!hasVoice) {
          console.debug('[ConvReg] Audio RMS too low — skipping transcription (silence/noise)');
          return;
        }

        const ext = usedMime.includes('mp4') ? 'm4a'
                  : usedMime.includes('ogg') ? 'ogg'
                  : 'webm';

        const formData = new FormData();
        formData.append('audio', audioBlob, `recording.${ext}`);
        formData.append('language', language);

        setIsProcessing(true);
        try {
          const transcribeRes = await faceApi.post('/transcribe', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 30000,
          });

          const transcript: string = (transcribeRes.data?.transcription || '').trim();
          // Guard against punctuation-only "transcripts" (e.g. a stray '.')
          // which carry no real speech but would otherwise look truthy.
          if (!transcript || !/[a-zA-Z\u0B80-\u0BFF0-9]/.test(transcript)) {
            setIsProcessing(false);
            return;
          }

          await sendToLLM(transcript);
        } catch (err: any) {
          console.error('[ConvReg] Transcription failed:', err);
          setIsProcessing(false);
          isProcessingRef.current = false;  // unlock pipeline
        }
      };

      mediaRecorderRef.current.onerror = () => {
        setIsRecording(false);
      };

      mediaRecorderRef.current.start(100);
      setIsRecording(true);
    } catch (err) {
      console.error('[ConvReg] VAD startRecording error:', err);
    }
  }, [micStream, isRecording, language, sendToLLM]);

  // VAD Callback: Silence detected, stop recording
  const handleSpeechEnd = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      try { mediaRecorderRef.current.requestData(); } catch { /* ignore */ }
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  // Hook up VAD
  const { volume } = useVAD({
    stream: micStream,
    paused: isSpeaking || isProcessing,
    onSpeechStart: handleSpeechStart,
    onSpeechEnd: handleSpeechEnd,
    threshold: 15, // High sensitivity for human voices
    silenceDelayMs: 0, // No delay
  });

  const stopListening = useCallback(() => {
    micStream?.getTracks().forEach(t => t.stop());
    setMicStream(null);
    setIsRecording(false);
  }, [micStream]);

  const reset = useCallback(() => {
    abortControllerRef.current?.abort();
    micStream?.getTracks().forEach(t => t.stop());
    setMicStream(null);
    setIsRecording(false);
    setIsProcessing(false);
    setHistory([]);
    setCollectedFields({ name: null, age: null, phone: null, blood_group: null, city: null });
    setAllCollected(false);
    setLastReply('');
    setError(null);
    isProcessingRef.current = false;
  }, [micStream]);

  const sendText = useCallback(async (text: string) => {
    if (!text.trim() || isProcessingRef.current) return;
    await sendToLLM(text);
  }, [sendToLLM]);

  return {
    isRecording,
    isProcessing,
    isSpeaking,
    volume,
    isListeningMode: !!micStream,
    history,
    collectedFields,
    setCollectedFields,
    allCollected,
    lastReply,
    error,
    initListening,
    stopListening,
    sendText,
    reset,
  };
}
