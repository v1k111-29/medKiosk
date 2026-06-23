import { useEffect, useRef, useState, useCallback } from 'react';

interface UseVADOptions {
  stream: MediaStream | null;
  /** Volume threshold (0-100) above which speech is detected */
  threshold?: number;
  /** Milliseconds of silence before triggering onSpeechEnd */
  silenceDelayMs?: number;
  /** Maximum milliseconds to record before forcing a stop (prevents infinite noise loops) */
  maxDurationMs?: number;
  /** Pause VAD processing (e.g., when TTS is speaking) */
  paused?: boolean;
  onSpeechStart?: () => void;
  onSpeechEnd?: () => void;
}

export function useVAD({
  stream,
  threshold = 15, // Adjusted for typical microphone levels
  silenceDelayMs = 1500, // 1.5 seconds of silence means they stopped speaking
  maxDurationMs = 8000, // 8 seconds maximum per turn to force conversation flow
  paused = false,
  onSpeechStart,
  onSpeechEnd,
}: UseVADOptions) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [volume, setVolume] = useState(0);

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const requestFrameRef = useRef<number>(0);
  
  const isSpeakingRef = useRef(false);
  const silenceStartRef = useRef<number | null>(null);
  const speechStartRef = useRef<number | null>(null);
  const lastSpeechEndRef = useRef<number>(0);
  const pausedRef = useRef(paused);
  
  // Keep callbacks fresh without re-triggering effect
  const cbRef = useRef({ onSpeechStart, onSpeechEnd });
  useEffect(() => {
    cbRef.current = { onSpeechStart, onSpeechEnd };
  }, [onSpeechStart, onSpeechEnd]);

  useEffect(() => {
    pausedRef.current = paused;
    if (paused) {
      // If paused mid-speech, immediately consider speech ended 
      // so we don't hold the mic open indefinitely
      if (isSpeakingRef.current) {
        isSpeakingRef.current = false;
        setIsSpeaking(false);
        silenceStartRef.current = null;
        speechStartRef.current = null;
        lastSpeechEndRef.current = Date.now();
        cbRef.current.onSpeechEnd?.();
      }
    }
  }, [paused]);

  useEffect(() => {
    if (!stream || stream.getAudioTracks().length === 0) return;

    // Standardize AudioContext across browsers
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) {
      console.warn('[VAD] Web Audio API not supported in this browser');
      return;
    }

    try {
      const ctx = new AudioContextClass();
      audioContextRef.current = ctx;

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.4;
      analyserRef.current = analyser;

      const source = ctx.createMediaStreamSource(stream);
      source.connect(analyser);
      sourceRef.current = source;

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const checkVolume = () => {
        if (!analyserRef.current || pausedRef.current) {
          // If paused, just loop but do nothing
          if (pausedRef.current) {
            setVolume(0);
          }
          requestFrameRef.current = requestAnimationFrame(checkVolume);
          return;
        }

        analyserRef.current.getByteFrequencyData(dataArray);

        // Calculate average volume
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const avgVolume = sum / bufferLength;
        setVolume(avgVolume);

        const speakingNow = avgVolume > threshold;

        // Cool-down period after ending speech to prevent immediate re-triggering 
        // due to state update delays in the parent component
        const inCooldown = Date.now() - lastSpeechEndRef.current < 500;

        if (speakingNow && !inCooldown) {
          silenceStartRef.current = null;
          if (!isSpeakingRef.current) {
            isSpeakingRef.current = true;
            speechStartRef.current = Date.now();
            setIsSpeaking(true);
            cbRef.current.onSpeechStart?.();
          } else {
            // Check max duration
            if (speechStartRef.current && Date.now() - speechStartRef.current > maxDurationMs) {
              isSpeakingRef.current = false;
              setIsSpeaking(false);
              silenceStartRef.current = null;
              speechStartRef.current = null;
              lastSpeechEndRef.current = Date.now();
              cbRef.current.onSpeechEnd?.();
            }
          }
        } else {
          if (isSpeakingRef.current) {
            // Also check max duration even during silence delay
            if (speechStartRef.current && Date.now() - speechStartRef.current > maxDurationMs) {
              isSpeakingRef.current = false;
              setIsSpeaking(false);
              silenceStartRef.current = null;
              speechStartRef.current = null;
              lastSpeechEndRef.current = Date.now();
              cbRef.current.onSpeechEnd?.();
            } else if (silenceStartRef.current === null) {
              silenceStartRef.current = Date.now();
            } else if (Date.now() - silenceStartRef.current > silenceDelayMs) {
              isSpeakingRef.current = false;
              setIsSpeaking(false);
              silenceStartRef.current = null;
              speechStartRef.current = null;
              lastSpeechEndRef.current = Date.now();
              cbRef.current.onSpeechEnd?.();
            }
          }
        }

        requestFrameRef.current = requestAnimationFrame(checkVolume);
      };

      checkVolume();

    } catch (err) {
      console.error('[VAD] Failed to initialize AudioContext:', err);
    }

    return () => {
      cancelAnimationFrame(requestFrameRef.current);
      if (sourceRef.current) {
        sourceRef.current.disconnect();
      }
      if (audioContextRef.current?.state !== 'closed') {
        audioContextRef.current?.close().catch(() => {});
      }
    };
  }, [stream, threshold, silenceDelayMs]); // Re-run only if stream or core config changes

  return { isSpeaking, volume };
}
