import React, { useState, useEffect } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { useVoiceTriage } from '../hooks/useVoiceTriage';
import { Mic, Send, Loader2, ChevronLeft, Square, AlertTriangle } from 'lucide-react';
import { detectDeptId } from '../data/departments';
import { triageSymptoms, bookAppointment, Urgency } from '../services/api';
import { Disclaimer } from '../components/Bilingual';

const L = {
  en: {
    title: 'How are you feeling today?',
    sub: 'Type or speak your symptoms in Tamil or English.',
    placeholder: 'e.g. I have fever and headache since yesterday…',
    startSpeak: 'Tap to Speak',
    stopSpeak: 'Stop Recording',
    listening: 'Listening…',
    analyze: 'Analyze & Route',
    analyzing: 'Analysing…',
    back: 'Back',
    tts: 'Please describe your symptoms by typing or speaking.',
  },
  ta: {
    title: 'இன்று எப்படி உணர்கிறீர்கள்?',
    sub: 'உங்கள் அறிகுறிகளை தமிழ் அல்லது ஆங்கிலத்தில் சொல்லுங்கள்.',
    placeholder: 'எ.கா. நேற்றிலிருந்து காய்ச்சல் மற்றும் தலைவலி உள்ளது…',
    startSpeak: 'குரல் உதவியாளரைத் தொடங்கவும்',
    stopSpeak: 'கவனிக்கிறது...',
    listening: 'கேட்கிறது…',
    analyze: 'பகுப்பாய்வு செய்யவும்',
    analyzing: 'பகுப்பாய்வு…',
    back: 'திரும்பு',
    tts: 'உங்கள் அறிகுறிகளை தட்டச்சு செய்யுங்கள் அல்லது பேசுங்கள்.',
  },
};

const Triage: React.FC = () => {
  const { language, patient, setStep, setTriage, setBooking } = useKioskStore();
  const { speak } = useTTS();
  // Triage allows mixed Tamil/English speech, so let Whisper auto-detect
  // the language per recording rather than forcing one.
  const {
    initListening, stopListening, isListeningMode, volume,
    isRecording, isProcessing,
    transcription, setTranscription, error: voiceError, clearError,
  } = useVoiceTriage({ language: 'auto' });
  const [loading, setLoading] = useState(false);
  const t = L[language];

  useEffect(() => { 
    speak(t.tts); 
    initListening();
  }, [initListening, speak, t.tts]);

  // The server decides urgency (LLM advisory + red-flag rules + NEWS2 from today's vitals).
  // The kiosk never hardcodes urgency; booking re-checks server-side and can only raise it.
  const handleAnalyze = async () => {
    const text = transcription.trim();
    if (!text) return;
    setLoading(true);
    speak(language === 'ta' ? 'அறிகுறிகள் பகுப்பாய்வு செய்யப்படுகின்றன.' : 'Analysing your symptoms.');
    let deptId = detectDeptId(text);
    let urgency: Urgency = 'normal';
    let reasons: string[] = [];
    try {
      const r = await triageSymptoms(text, 'auto', patient?.id, patient?.age);
      if (r.dept_id) deptId = r.dept_id;
      urgency = r.urgency;
      reasons = r.escalation_reasons ?? [];
    } catch (err) {
      // Offline: keyword dept only. /appointment/book still applies the safety rules.
      console.error('[Triage] server triage failed:', err);
    }
    // Keep the patient's own words for staff; the server re-checks them at booking.
    setTriage({ symptoms: text, deptId, urgency, escalationReasons: reasons });

    if (urgency === 'emergency') {
      // Book straight into the emergency queue (alerts staff), then show the ER screen.
      if (patient?.id) {
        try {
          const appt = await bookAppointment({
            patient_id: patient.id, dept_id: 'emergency', symptoms: text,
            service: 'emergency', urgency: 'emergency', sms_opt_in: false,
            doctor_id: null, doctor_name: null,
          });
          setBooking(appt);
        } catch (err) {
          console.error('[Triage] emergency booking failed:', err);
        }
      }
      setLoading(false);
      setStep('EMERGENCY');
      return;
    }
    setLoading(false);
    setStep('DEPARTMENT');
  };

  const ta = language === 'ta';

  const handleMicToggle = () => {
    clearError();
    if (isListeningMode) stopListening();
    else initListening();
  };

  const VOICE_ERROR_MSG: Record<string, { en: string; ta: string }> = {
    mic_permission_denied: {
      en: 'Microphone access is blocked. Please allow microphone permission in your browser.',
      ta: 'மைக்ரோஃபோன் அனுமதி தடுக்கப்பட்டுள்ளது. அனுமதி வழங்கவும்.',
    },
    mic_not_found: {
      en: 'No microphone found. Please check your device.',
      ta: 'மைக்ரோஃபோன் கண்டறியப்படவில்லை.',
    },
    too_short: {
      en: 'Recording was too short — hold the button a little longer and speak.',
      ta: 'பதிவு மிகக் குறுகியது — சற்று நீண்ட நேரம் பேசவும்.',
    },
    transcribe_failed: {
      en: 'Voice processing failed. Please try again.',
      ta: 'குரல் செயலாக்கம் தோல்வியடைந்தது. மீண்டும் முயற்சிக்கவும்.',
    },
    no_speech: {
      en: "Couldn't hear any words — please try again.",
      ta: 'வார்த்தைகள் கேட்கவில்லை — மீண்டும் முயற்சிக்கவும்.',
    },
  };

  return (
    <div className="p-6 h-full flex flex-col bg-[#F2F6FA]">
      <div className="mb-5">
        <h1 className="text-3xl font-bold text-[#1A2B4A]"
          style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
          {t.title}
        </h1>
        <p className="text-base text-[#4A5C78] mt-1">{t.sub}</p>
      </div>

      {voiceError && (
        <div className="mb-3 bg-red-50 border-2 border-red-200 text-red-700 rounded-2xl px-5 py-3
          flex items-center gap-3 text-sm font-medium">
          <AlertTriangle size={20} className="flex-shrink-0" />
          {ta ? VOICE_ERROR_MSG[voiceError]?.ta : VOICE_ERROR_MSG[voiceError]?.en}
        </div>
      )}

      <Disclaimer lang={language} className="mb-3" />

      <textarea
        className="flex-1 w-full p-5 text-lg rounded-3xl border-2 border-white shadow-lg
          focus:border-[#2E7D96] outline-none resize-none bg-white transition-all"
        placeholder={t.placeholder}
        value={transcription}
        onChange={e => setTranscription(e.target.value)}
        style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}
      />

      <div className="flex gap-4 mt-5">
        <button
          onClick={() => setStep('MENU')}
          className="flex items-center gap-2 bg-white border-2 border-[#DDE4EE] text-[#4A5C78]
            px-6 py-4 rounded-2xl font-semibold hover:border-[#2E7D96] transition-all">
          <ChevronLeft size={20} /> {t.back}
        </button>

        <button
          onClick={handleMicToggle}
          aria-label={isRecording ? "Stop recording" : "Tap to speak"}
          disabled={isProcessing}
          className={`flex-1 flex items-center justify-center gap-3 py-4 rounded-2xl text-lg font-bold
            transition-all border-2 relative overflow-hidden ${isRecording
              ? 'bg-red-500 border-red-500 text-white animate-pulse shadow-red-200 shadow-lg'
              : isProcessing
                ? 'bg-orange-100 border-orange-300 text-orange-600 cursor-not-allowed'
              : !isListeningMode
                ? 'bg-white border-[#DDE4EE] text-[#1A2B4A] hover:border-[#2E7D96]'
                : 'bg-green-500 border-green-500 text-white'}`}
        >
          {/* Dynamic volume background width for listening mode */}
          {isListeningMode && !isRecording && !isProcessing && (
            <div 
              className="absolute left-0 top-0 bottom-0 bg-green-400 opacity-50 transition-all duration-100" 
              style={{ width: `${volume}%` }} 
            />
          )}
          <div className="relative z-10 flex items-center gap-3">
            {isProcessing ? <Loader2 className="animate-spin" /> : isRecording ? <Mic size={24} /> : <Mic size={24} />}
            {isRecording ? t.stopSpeak : isProcessing ? t.analyzing : !isListeningMode ? t.startSpeak : 'Speak now (hands-free)'}
          </div>
        </button>

        <button
          onClick={handleAnalyze}
          disabled={loading || isProcessing || isRecording || !transcription.trim()}
          className="flex-1 flex items-center justify-center gap-3 bg-[#2E7D96] hover:bg-[#236d84]
            disabled:opacity-40 text-white py-4 rounded-2xl text-lg font-bold shadow-lg
            active:scale-95 transition-all">
          {loading
            ? <><Loader2 size={22} className="animate-spin" />{t.analyzing}</>
            : <><Send size={22} />{t.analyze}</>}
        </button>
      </div>
    </div>
  );
};

export default Triage;
