import { useState, useRef, useCallback, useEffect } from 'react';
import { faceApi } from '../services/api';
import { useVAD } from './useVAD';

export type VoiceError =
  | 'mic_permission_denied'
  | 'mic_not_found'
  | 'too_short'
  | 'transcribe_failed'
  | 'no_speech'
  | null;

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
    console.debug(`[Triage] Audio RMS energy: ${rms.toFixed(5)}`);
    return rms > 0.008;
  } catch {
    return true; // on decode error, let Whisper decide
  }
  --- end original --- */
}

interface UseVoiceTriageOptions {
  language?: 'en' | 'ta' | 'auto';
  paused?: boolean; // pass isSpeaking or isProcessing from caller to pause VAD
}

export const useVoiceTriage = (options: UseVoiceTriageOptions = {}) => {
  const { language = 'auto', paused = false } = options;

  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcription, setTranscription] = useState('');
  const [error, setError] = useState<VoiceError>(null);

  const [micStream, setMicStream] = useState<MediaStream | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startTimeRef = useRef<number>(0);
  const isProcessingRef = useRef(false);

  useEffect(() => {
    return () => {
      micStream?.getTracks().forEach(t => t.stop());
    };
  }, [micStream]);

  const initListening = useCallback(async () => {
    if (micStream || isProcessingRef.current) return;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('mic_not_found');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setMicStream(stream);
    } catch (err: any) {
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        setError('mic_permission_denied');
      } else {
        setError('mic_not_found');
      }
    }
  }, [micStream]);

  const appendOrReplace = (newText: string, mode: 'append' | 'replace') => {
    setTranscription(prev => {
      if (mode === 'replace') return newText;
      return prev ? `${prev} ${newText}` : newText;
    });
  };

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
          // Ignore short glitches silently
          return;
        }

        // RMS energy guard: skip transcription if the audio is just ambient
        // noise / silence — no point sending it to Groq Whisper.
        const hasVoice = await checkAudioHasVoice(audioBlob);
        if (!hasVoice) {
          console.debug('[Triage] Audio RMS too low — skipping transcription (silence/noise)');
          return;
        }

        const ext = usedMime.includes('mp4') ? 'm4a'
                  : usedMime.includes('ogg') ? 'ogg'
                  : 'webm';

        const formData = new FormData();
        formData.append('audio', audioBlob, `recording.${ext}`);
        formData.append('language', language);

        setIsProcessing(true);
        isProcessingRef.current = true;
        try {
          const res = await faceApi.post('/transcribe', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });

          const transcript = (res.data?.transcription || '').trim();
          // Guard against punctuation-only "transcripts" (e.g. a stray '.')
          // which carry no real speech but would otherwise look truthy.
          if (transcript && /[a-zA-Z\u0B80-\u0BFF0-9]/.test(transcript)) {
            appendOrReplace(transcript, 'replace'); // replace for single turn in triage
          } else {
            setError('no_speech');
          }
        } catch (err: any) {
          console.error('[Voice] /transcribe failed:', err);
          if (err?.response?.status === 422) {
            setError('no_speech');
          } else if (err?.response?.status === 400 && err?.response?.data?.message) {
            // too short, but ignore to not annoy patient
          } else {
            setError('transcribe_failed');
          }
        } finally {
          setIsProcessing(false);
          isProcessingRef.current = false;
        }
      };

      mediaRecorderRef.current.onerror = () => {
        setIsRecording(false);
      };

      mediaRecorderRef.current.start(100);
      setIsRecording(true);
    } catch (err) {
      console.error('[Voice] VAD start error:', err);
    }
  }, [micStream, isRecording, language]);

  const handleSpeechEnd = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      try { mediaRecorderRef.current.requestData(); } catch { /* ignore */ }
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  const { volume } = useVAD({
    stream: micStream,
    paused: paused || isProcessing,
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

  const resetTranscription = useCallback(() => {
    setTranscription('');
    setError(null);
  }, []);

  return {
    initListening,
    stopListening,
    isListeningMode: !!micStream,
    isRecording,
    isProcessing,
    volume,
    transcription,
    setTranscription,
    resetTranscription,
    error,
    clearError: () => setError(null),
  };
};
