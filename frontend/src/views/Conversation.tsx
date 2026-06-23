import React, { useEffect, useRef, useState } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { useVoiceTriage, VoiceError } from '../hooks/useVoiceTriage';
import { useConversation } from '../hooks/useConversation';
import { faceApi } from '../services/api';
import { Mic, MicOff, Square, Loader2, Bot, User, ChevronRight, AlertTriangle, Calendar } from 'lucide-react';
import StepBar from '../components/StepBar';

const VOICE_ERROR_MSG: Record<string, string> = {
  mic_permission_denied: 'Microphone access is blocked. Please allow microphone permission for this site.',
  mic_not_found:         'No microphone found. Please check your device.',
  too_short:             'That was too short — hold the mic longer and speak clearly.',
  transcribe_failed:     'Voice processing failed. Please try again or use the touch menu.',
  no_speech:             "I didn't catch any words — please try speaking again.",
};

// Department display names map (matches backend dept_id)
const DEPT_DISPLAY: Record<string, { name: string; nameTa: string }> = {
  general:   { name: 'General OPD',    nameTa: 'பொது OPD' },
  cardio:    { name: 'Cardiology',     nameTa: 'இதய நோய்கள்' },
  ortho:     { name: 'Orthopedics',    nameTa: 'எலும்பு அறுவை சிகிச்சை' },
  paeds:     { name: 'Paediatrics',    nameTa: 'குழந்தை நோய்' },
  gyne:      { name: 'Gynaecology',    nameTa: 'மகளிர் நோய்கள்' },
  derm:      { name: 'Dermatology',    nameTa: 'தோல் நோய்கள்' },
  ent:       { name: 'ENT',            nameTa: 'காது மூக்கு தொண்டை' },
  ophthal:   { name: 'Ophthalmology',  nameTa: 'கண் நோய்கள்' },
  emergency: { name: 'Emergency',      nameTa: 'அவசர சிகிச்சை' },
};

interface Doctor {
  id: number;
  name: string;
  qualification: string;
  available: boolean;
}

interface PendingBooking {
  dept_id:   string;
  dept_name: string;
  room:      string;
  wait_mins: number;
  symptoms:  string | null;
  service:   string;
  urgency:   string;
  reply:     string;
  doctor_id:   number | null;
  doctor_name: string | null;
  doctors:     Doctor[];
}

const Conversation: React.FC = () => {
  const { patient, language, setStep, setTriage, setToken } = useKioskStore();
  const { speak, cancel: stopTTS, isSpeaking } = useTTS();



  const { messages, isAILoading, processText, addMessage } = useConversation();

  // Pending booking: set after LLM returns dept info, waiting for patient to confirm
  const [pendingBooking, setPendingBooking] = useState<PendingBooking | null>(null);
  const [isBooking, setIsBooking] = useState(false);

  const {
    initListening, stopListening, isListeningMode, isRecording, isProcessing, volume,
    transcription, setTranscription, resetTranscription, error: voiceError, clearError,
  } = useVoiceTriage({ language: 'en', paused: isSpeaking || isBooking || isAILoading });

  const sentRef  = useRef(false);
  const welcomeSpokenRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // ── Welcome message ────────────────────────────────────────────────────────
  useEffect(() => {
    if (language === 'ta') { setStep('MENU'); return; }
    if (welcomeSpokenRef.current) return;
    
    welcomeSpokenRef.current = true;
    const name = patient?.name?.split(' ')[0] || 'there';
    const welcome =
      `Welcome back, ${name}! I'm your AI assistant. ` +
      `Please tell me your symptoms or say which department you'd like to visit, ` +
      `and I'll book your appointment right away.`;
    addMessage('ai', welcome);
    speak(welcome, 'en');
    initListening();
  }, [initListening, language, patient, addMessage, speak, setStep]);

  // ── Auto-scroll ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, transcription, voiceError]);

  const handleMicToggle = async () => {
    if (isListeningMode) {
      stopListening();
    } else {
      stopTTS();
      clearError();
      sentRef.current = false;
      resetTranscription();
      await initListening();
    }
  };

  // ── Fire once per completed transcription ──────────────────────────────────
  useEffect(() => {
    if (isRecording) {
      sentRef.current = false;
      resetTranscription();
      return;
    }
    if (isProcessing) return;
    if (!transcription.trim()) return;
    if (sentRef.current) return;

    sentRef.current = true;
    handleUserSpeech(transcription);
  }, [isRecording, isProcessing, transcription]);

  // ── Core: handle what the patient says ────────────────────────────────────
  const handleUserSpeech = async (text: string) => {
    // If we are awaiting confirmation of a pending booking
    if (pendingBooking) {
      const lower = text.toLowerCase();
      const isYes = /\b(yes|yeah|yep|correct|right|sure|okay|ok|go ahead|please|confirm|book|proceed)\b/.test(lower);
      const isNo  = /\b(no|nope|not|wrong|different|change|cancel|skip)\b/.test(lower);

      if (isYes) {
        await doBook(pendingBooking);
        return;
      }
      if (isNo) {
        setPendingBooking(null);
        const retry = "Of course. Could you tell me what you'd like help with instead?";
        addMessage('ai', retry);
        speak(retry, 'en');
        return;
      }
      // Check if user mentioned a doctor's name
      if (pendingBooking.doctors?.length) {
        const matchedDoc = pendingBooking.doctors.find(d =>
          lower.includes(d.name.toLowerCase().split(' ').pop() || '')
        );
        if (matchedDoc) {
          await doBook({ ...pendingBooking, doctor_id: matchedDoc.id, doctor_name: matchedDoc.name });
          return;
        }
      }
      // Ambiguous — treat as new utterance
      setPendingBooking(null);
    }

    // Send to LLM general conversation handler
    const response = await processText(text);
    if (!response) return;

    speak(response.reply, 'en');

    // If intent requires triage, run triage call
    const triageIntents = ['symptoms', 'appointment', 'followup', 'emergency'];
    if (triageIntents.includes(response.intent) && !pendingBooking) {
      // Call triage endpoint for dept + booking info
      await runTriage(text, response.intent);
    }
  };

  // ── Triage: ask LLM for dept routing ──────────────────────────────────────
  const runTriage = async (text: string, intent: string) => {
    try {
      const res = await faceApi.post('/conversation/triage', { text, language: 'en' });
      const data = res.data;

      const deptId = data.dept_id || 'general';

      // Fetch available doctors for this department
      let doctors: Doctor[] = [];
      try {
        const docRes = await faceApi.get(`/doctors?dept_id=${deptId}`);
        doctors = (docRes.data?.doctors || []).filter((d: Doctor) => d.available);
      } catch { /* ignore */ }

      const booking: PendingBooking = {
        dept_id:   deptId,
        dept_name: data.dept_name || 'General OPD',
        room:      data.room      || 'OPD-1',
        wait_mins: data.wait_mins ?? 20,
        symptoms:  data.symptoms  || text,
        service:   data.service   || intent,
        urgency:   data.urgency   || 'normal',
        reply:     data.reply     || '',
        doctor_id:   null,
        doctor_name: null,
        doctors,
      };

      // Emergency: book immediately without confirmation
      if (booking.urgency === 'emergency') {
        const urgentMsg = '🚨 This sounds urgent! I am booking you into Emergency right now.';
        addMessage('ai', urgentMsg);
        speak(urgentMsg, 'en');
        await doBook({ ...booking, dept_id: 'emergency', dept_name: 'Emergency', room: 'Emergency', wait_mins: 0 });
        return;
      }

      const deptDisplay = DEPT_DISPLAY[booking.dept_id] || { name: booking.dept_name };
      const docNames = doctors.map(d => d.name).join(' or ');
      const docPart = docNames ? ` Available doctors: ${docNames}.` : '';
      const confirmMsg =
        `${data.reply || ''} ` +
        `I'll book you into ${deptDisplay.name}, ${booking.room}. ` +
        `Estimated wait: ~${booking.wait_mins} minutes.${docPart} ` +
        `Shall I confirm? You can also say a doctor's name if you have a preference.`;

      addMessage('ai', confirmMsg);
      speak(confirmMsg, 'en');
      setPendingBooking(booking);

    } catch (err) {
      console.error('[Conversation] Triage call failed:', err);
      const msg = "I'm having trouble routing you. Please use the touch menu.";
      addMessage('ai', msg);
      speak(msg, 'en');
    }
  };

  // ── Book: call backend, store result, navigate to CONFIRM ─────────────────
  const doBook = async (booking: PendingBooking) => {
    if (!patient?.id) {
      addMessage('ai', "I can't find your patient record. Please register first.");
      return;
    }

    setIsBooking(true);
    setPendingBooking(null);
    addMessage('ai', `Booking your appointment at ${booking.dept_name}…`);

    try {
      const res = await faceApi.post('/appointment/book', {
        patient_id:  patient.id,
        dept_id:     booking.dept_id,
        dept_name:   booking.dept_name,
        room:        booking.room,
        symptoms:    booking.symptoms,
        service:     booking.service,
        wait_mins:   booking.wait_mins,
        doctor_id:   booking.doctor_id || null,
        doctor_name: booking.doctor_name || null,
      });

      const appt = res.data;
      const deptDisplay = DEPT_DISPLAY[booking.dept_id] || { name: booking.dept_name };

      // Store triage info + token in kiosk store
      setTriage({
        service:    booking.service as any,
        symptoms:   booking.symptoms || '',
        deptId:     booking.dept_id,
        deptName:   deptDisplay.name,
        deptNameTa: deptDisplay.nameTa || deptDisplay.name,
        room:       booking.room,
        waitMins:   booking.wait_mins,
        doctorId:   booking.doctor_id || null,
        doctorName: booking.doctor_name || '',
      });
      setToken(appt.token);

      const docInfo = booking.doctor_name ? ` Your doctor: ${booking.doctor_name}.` : '';
      const doneMsg =
        `✅ You're booked! Token: ${appt.token}. ` +
        `Please go to ${booking.dept_name}, ${booking.room}.${docInfo} ` +
        `Estimated wait: ~${booking.wait_mins} minutes.`;
      addMessage('ai', doneMsg);
      speak(doneMsg, 'en');

      // Navigate to vitals form after brief pause
      setTimeout(() => setStep('VITALS'), 2500);

    } catch (err: any) {
      console.error('[Conversation] Booking failed:', err);
      const msg = err?.response?.data?.detail || "Booking failed. Please try again.";
      addMessage('ai', msg);
      speak(msg, 'en');
    } finally {
      setIsBooking(false);
    }
  };

  const errorMsg = voiceError ? VOICE_ERROR_MSG[voiceError] : null;
  const isBusy   = isAILoading || isProcessing || isBooking;

  return (
    <div className="flex flex-col h-full bg-[#F2F6FA]">
      <div className="p-4">
        <StepBar />
      </div>

      {/* ── Chat messages ── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 space-y-4 py-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'ai' ? 'justify-start' : 'justify-end'}`}>
            <div className={`flex gap-3 max-w-[80%] ${m.role === 'ai' ? 'flex-row' : 'flex-row-reverse'}`}>
              <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0
                ${m.role === 'ai' ? 'bg-[#2E7D96] text-white' : 'bg-white text-[#4A5C78] border-2 border-[#DDE4EE]'}`}>
                {m.role === 'ai' ? <Bot size={20} /> : <User size={20} />}
              </div>
              <div className={`p-4 rounded-2xl shadow-sm text-lg font-medium
                ${m.role === 'ai'
                  ? 'bg-white text-[#1A2B4A] rounded-tl-none'
                  : 'bg-[#2E7D96] text-white rounded-tr-none'}`}>
                {m.text}
              </div>
            </div>
          </div>
        ))}

        {/* Pending booking confirmation card */}
        {pendingBooking && (
          <div className="flex justify-start">
            <div className="bg-[#E8F5E9] border-2 border-[#4CAF50] rounded-2xl p-4 max-w-sm w-full shadow-md">
              <div className="flex items-center gap-2 mb-3">
                <Calendar size={20} className="text-[#2E7D5C]" />
                <span className="font-bold text-[#1A2B4A]">Confirm Appointment</span>
              </div>
              <div className="space-y-1 text-sm text-[#4A5C78] mb-3">
                <p><span className="font-semibold">Department:</span> {pendingBooking.dept_name}</p>
                <p><span className="font-semibold">Room:</span> {pendingBooking.room}</p>
                <p><span className="font-semibold">Est. Wait:</span> ~{pendingBooking.wait_mins} min</p>
                {pendingBooking.symptoms && (
                  <p><span className="font-semibold">Reason:</span> {pendingBooking.symptoms}</p>
                )}
              </div>

              {/* Doctor selection */}
              {pendingBooking.doctors?.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs font-semibold text-[#8A9BB5] uppercase tracking-wider mb-2">Select Doctor</p>
                  <div className="space-y-1.5">
                    {pendingBooking.doctors.map(doc => (
                      <button
                        key={doc.id}
                        onClick={() => setPendingBooking(prev => prev ? { ...prev, doctor_id: doc.id, doctor_name: doc.name } : null)}
                        className={`w-full text-left px-3 py-2 rounded-xl text-sm transition-all flex items-center gap-2 border
                          ${pendingBooking.doctor_id === doc.id
                            ? 'bg-[#2E7D96] text-white border-[#2E7D96] font-bold'
                            : 'bg-white text-[#4A5C78] border-[#DDE4EE] hover:border-[#2E7D96]'
                          }`}
                      >
                        <span className="flex-1">{doc.name}</span>
                        <span className={`text-xs ${pendingBooking.doctor_id === doc.id ? 'text-white/80' : 'text-[#8A9BB5]'}`}>
                          {doc.qualification}
                        </span>
                      </button>
                    ))}
                    <button
                      onClick={() => setPendingBooking(prev => prev ? { ...prev, doctor_id: null, doctor_name: null } : null)}
                      className={`w-full text-left px-3 py-2 rounded-xl text-sm transition-all border
                        ${!pendingBooking.doctor_id
                          ? 'bg-[#2E7D96] text-white border-[#2E7D96] font-bold'
                          : 'bg-white text-[#8A9BB5] border-[#DDE4EE] hover:border-[#2E7D96]'
                        }`}
                    >
                      No preference
                    </button>
                  </div>
                </div>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => doBook(pendingBooking)}
                  className="flex-1 bg-[#2E7D96] text-white py-2 rounded-xl font-bold hover:bg-[#236d84] active:scale-95 transition-all"
                >
                  ✓ Yes, Book It
                </button>
                <button
                  onClick={() => {
                    setPendingBooking(null);
                    const m = "No problem. What else can I help you with?";
                    addMessage('ai', m); speak(m, 'en');
                  }}
                  className="flex-1 bg-white border-2 border-[#DDE4EE] text-[#4A5C78] py-2 rounded-xl font-bold hover:border-red-300 transition-all"
                >
                  ✗ Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {isRecording && (
          <div className="flex justify-end">
            <div className="bg-[#E3F2F7] text-[#2E7D96] p-4 rounded-2xl border-2 border-[#2E7D96] animate-pulse">
              🎤 Listening… speak now
            </div>
          </div>
        )}
        {isProcessing && (
          <div className="flex justify-end">
            <div className="bg-[#FEF3C7] text-[#92400E] p-4 rounded-2xl flex items-center gap-3">
              <Loader2 className="animate-spin" size={18} /> Transcribing…
            </div>
          </div>
        )}
        {(isAILoading || isBooking) && (
          <div className="flex justify-start">
            <div className="bg-white p-4 rounded-2xl flex items-center gap-3 text-[#2E7D96]">
              <Loader2 className="animate-spin" />
              {isBooking ? 'Booking your appointment…' : 'Thinking…'}
            </div>
          </div>
        )}
        {errorMsg && (
          <div className="flex justify-center">
            <div className="bg-red-50 border-2 border-red-200 text-red-700 p-4 rounded-2xl flex items-center gap-3 max-w-md text-sm font-medium">
              <AlertTriangle size={20} className="flex-shrink-0" />
              {errorMsg}
            </div>
          </div>
        )}
      </div>

      {/* ── Mic bar (Hands-free) ── */}
      <div className="p-8 bg-white border-t border-[#DDE4EE] flex items-center gap-6">
        <button
          onClick={handleMicToggle}
          disabled={isBusy || isSpeaking}
          className={`w-24 h-24 rounded-full flex items-center justify-center transition-all shadow-xl select-none relative
            disabled:opacity-50 disabled:cursor-not-allowed
            ${isRecording
              ? 'bg-red-500 text-white animate-pulse ring-4 ring-red-300'
              : isSpeaking
                ? 'bg-amber-400 text-white'
              : !isListeningMode
                ? 'bg-[#2E7D96] text-white hover:bg-[#236d84] animate-pulse'
                : 'bg-green-500 hover:bg-green-600 text-white'}`}
        >
          {/* Dynamic volume ring */}
          {isListeningMode && !isRecording && !isBusy && !isSpeaking && (
            <div
              className="absolute inset-0 rounded-full border-4 border-green-300 opacity-50"
              style={{ transform: `scale(${1 + volume / 80})`, transition: 'transform 0.1s' }}
            />
          )}
          {isBusy
            ? <Loader2 size={32} className="animate-spin" />
            : isRecording ? <MicOff size={32} /> : <Mic size={32} />}
        </button>
        <div className="flex-1">
          <p className="text-[#8A9BB5] font-semibold uppercase tracking-widest text-xs mb-1">
            {isSpeaking  ? 'AI is speaking…'
              : isBooking  ? 'Booking your appointment…'
              : isRecording ? 'Hearing you...'
              : isProcessing ? 'Processing…'
              : pendingBooking ? 'Say "Yes" to confirm'
              : !isListeningMode ? 'Tap to start voice assistant'
              : 'Speak now (hands-free)'}
          </p>
          <h3 className="text-xl font-bold text-[#1A2B4A]">
            {isSpeaking    ? 'Please wait, then speak to reply'
              : isBooking    ? 'Almost done…'
              : isRecording  ? 'I am listening to you…'
              : isProcessing ? 'Converting speech to text…'
              : errorMsg     ? 'Tap the mic to try again'
              : pendingBooking ? 'Confirm or cancel above, or say Yes / No'
              : 'How can I help you today?'}
          </h3>
        </div>
        <button
          onClick={() => setStep('MENU')}
          className="px-6 py-4 rounded-xl border-2 border-[#DDE4EE] text-[#4A5C78] font-bold flex items-center gap-2 hover:bg-gray-50"
        >
          Use Touch Menu <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
};

export default Conversation;
