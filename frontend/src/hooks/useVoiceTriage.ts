import { useState, useRef } from 'react';
import { whisperApi } from '../services/api';

export const useVoiceTriage = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [transcription, setTranscription] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const mediaRecorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const startTime = useRef<number>(0);

  const startRecording = async () => {
    console.log("[Voice] Requesting microphone access...");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      startTime.current = Date.now();
      console.log("[Voice] Stream acquired:", stream.id, "Active:", stream.active);
      
      const tracks = stream.getAudioTracks();
      console.log("[Voice] Audio tracks:", tracks.length, "State:", tracks[0]?.readyState);
      
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') 
        ? 'audio/webm' 
        : 'audio/ogg';
      
      console.log("[Voice] Using mimeType:", mimeType);
      mediaRecorder.current = new MediaRecorder(stream, { mimeType });
      chunks.current = [];

      mediaRecorder.current.ondataavailable = (e) => {
        if (e.data.size > 0) {
          console.log("[Voice] Data event received. Size:", e.data.size);
          chunks.current.push(e.data);
        }
      };

      mediaRecorder.current.onstop = async () => {
        const duration = Date.now() - startTime.current;
        console.log("[Voice] Recording stopped. Duration:", duration, "ms. Chunks:", chunks.current.length);
        
        const audioBlob = new Blob(chunks.current, { type: mimeType });
        console.log("[Voice] Audio Blob size:", audioBlob.size, "bytes");

        if (duration < 500 || audioBlob.size < 2000) {
          console.warn("[Voice] Recording too short or empty, ignoring.");
          setIsProcessing(false);
          return;
        }

        const formData = new FormData();
        formData.append('audio', audioBlob, 'triage.webm');

        setIsProcessing(true);
        try {
          console.log("[Voice] Sending to backend:", whisperApi.defaults.baseURL + "/transcribe");
          const res = await whisperApi.post('/transcribe', formData);
          console.log("[Voice] Backend Response:", res.data);
          
          if (res.data && res.data.transcription) {
            setTranscription(prev => prev ? `${prev} ${res.data.transcription}` : res.data.transcription);
          }
        } catch (err) {
          console.error("[Voice] API Call Failed:", err);
        } finally {
          setIsProcessing(false);
        }
      };

      mediaRecorder.current.start(); 
      console.log("[Voice] MediaRecorder started. Current state:", mediaRecorder.current.state);
      setIsRecording(true);
    } catch (err) {
      console.error("[Voice] Media access error:", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state === "recording") {
      console.log("[Voice] Requesting final data and stopping...");
      mediaRecorder.current.requestData();
      mediaRecorder.current.stop();
      setIsRecording(false);
      mediaRecorder.current.stream.getTracks().forEach(track => track.stop());
    }
  };

  return { 
    startRecording, 
    stopRecording, 
    isRecording, 
    isProcessing,
    transcription, 
    setTranscription 
  };
};
