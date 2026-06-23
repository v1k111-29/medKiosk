/**
 * Registration — Conversational AI-powered patient registration.
 *
 * Flow:
 *  1. Ollama greets the patient and asks for their name
 *  2. Patient presses mic → speaks → Whisper transcribes
 *  3. Transcript sent to Ollama → fields extracted, natural reply generated
 *  4. TTS speaks the reply, form auto-fills
 *  5. Patient can also type in any field manually at any time
 *  6. Once all fields collected (or patient presses Submit), register via /register
 */

import React, { useState, useEffect, useRef } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { useConversationalRegistration } from '../hooks/useConversationalRegistration';
import VoiceMicBtn from '../components/VoiceMicBtn';
import {
  UserPlus, CheckCircle, Loader2, Mic, MicOff,
  MessageSquare, Send, ChevronRight, Bot
} from 'lucide-react';
import { faceApi } from '../services/api';

const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'];

const L = {
  en: {
    title: 'New Patient Registration',
    subtitle: 'Speak naturally or fill in the form below',
    aiGreeting: "Hello! I'm here to help you register. Could you please tell me your full name?",
    holdSpeak: 'Tap to start voice assistant',
    releaseStop: 'Speak now (hands-free)',
    processing: 'Processing…',
    listening: 'Listening…',
    nameLabel: 'Full Name *',
    ageLabel: 'Age',
    phoneLabel: 'Mobile Number',
    genderLabel: 'Gender',
    genderDetected: 'AI detected',
    genderCorrect: 'Tap to change if incorrect',
    bloodLabel: 'Blood Group',
    cityLabel: 'City / Town',
    consentLabel: 'I consent to my biometric data being stored securely (DPDP Act 2023)',
    submitBtn: 'Complete Registration',
    submitLoading: 'Registering…',
    errName: 'Please provide your name to continue.',
    errConsent: 'Please accept the consent to register.',
    typeHint: 'Or type here…',
    sendBtn: 'Send',
    orType: 'Or fill manually:',
    skipVoice: 'Skip voice, fill manually',
    fieldsFilled: 'Details collected so far:',
  },
  ta: {
    title: 'புதிய நோயாளி பதிவு',
    subtitle: 'பேசுங்கள் அல்லது கீழே படிவத்தை நிரப்பவும்',
    aiGreeting: "வணக்கம்! நான் உங்களுக்கு பதிவு செய்ய உதவுகிறேன். உங்கள் முழு பெயரை சொல்லுங்கள்.",
    holdSpeak: 'பேச அழுத்தவும்',
    releaseStop: 'நிறுத்த விடவும்',
    processing: 'செயலாக்கம்…',
    listening: 'கேட்கிறேன்…',
    nameLabel: 'முழு பெயர் *',
    ageLabel: 'வயது',
    phoneLabel: 'மொபைல் எண்',
    genderLabel: 'பாலினம்',
    genderDetected: 'AI கண்டறிந்தது',
    genderCorrect: 'தவறாக இருந்தால் தட்டவும்',
    bloodLabel: 'இரத்த வகை',
    cityLabel: 'ஊர்',
    consentLabel: 'என் முக தரவை பாதுகாப்பாக சேமிக்க ஒப்புதல் தருகிறேன் (DPDP சட்டம் 2023)',
    submitBtn: 'பதிவை முடிக்கவும்',
    submitLoading: 'பதிவு செய்கிறது…',
    errName: 'தொடர பெயர் தேவை.',
    errConsent: 'பதிவு செய்ய ஒப்புதல் தேவை.',
    typeHint: 'இங்கே தட்டச்சு செய்யவும்…',
    sendBtn: 'அனுப்பு',
    orType: 'அல்லது கைமுறையாக நிரப்பவும்:',
    skipVoice: 'குரல் தவிர்க்கவும்',
    fieldsFilled: 'இதுவரை சேகரிக்கப்பட்ட விவரங்கள்:',
  },
};

const Registration: React.FC = () => {
  const { language, tempGender, tempEmbedding, setStep, setPatient } = useKioskStore();
  const [selectedGender, setSelectedGender] = useState<string>(tempGender || '');
  const { speak, cancel: cancelTTS, isSpeaking } = useTTS();
  const t = L[language];
  const ta = language === 'ta';

  // ── Conversational AI hook ───────────────────────────────────────────────
  const {
    isRecording, isProcessing, history,
    collectedFields, setCollectedFields,
    allCollected, lastReply, error: voiceError,
    initListening, isListeningMode, volume, sendText,
  } = useConversationalRegistration({
    language: 'en', // Whisper + Ollama work best in English for field extraction
    onFieldsExtracted: (extracted) => {
      // Auto-sync extracted fields into manual form
      setManualForm(prev => ({
        name:  extracted.name  ?? prev.name,
        age:   extracted.age   ?? prev.age,
        phone: extracted.phone ?? prev.phone,
        blood: extracted.blood_group ?? prev.blood,
        city:  extracted.city  ?? prev.city,
      }));
    },
    onAllCollected: () => {
      // Brief pause then suggest submitting
      setTimeout(() => {
        speak("I've got all your details. Please check them below and tap 'Complete Registration'.", 'en');
      }, 500);
    },
  });

  // ── Manual form state (kept in sync with AI extractions) ────────────────
  const [manualForm, setManualForm] = useState({
    name: '', age: '', phone: '', blood: '', city: '',
  });
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formError, setFormError] = useState('');
  const [textInput, setTextInput] = useState('');
  const [showManual, setShowManual] = useState(false);

  // Refs for scroll
  const chatEndRef = useRef<HTMLDivElement>(null);
  const textInputRef = useRef<HTMLInputElement>(null);
  const greetingSpokenRef = useRef(false);

  // ── Initial AI greeting ──────────────────────────────────────────────────
  useEffect(() => {
    if (greetingSpokenRef.current) return;
    greetingSpokenRef.current = true;
    
    const greeting = t.aiGreeting;
    // Send initial greeting as an assistant message
    setTimeout(() => {
      speak(greeting, 'en');
      // Auto-start listening after greeting begins
      initListening();
    }, 600);
  }, [initListening, t.aiGreeting, speak]);

  // Scroll chat to bottom when history changes
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history]);

  // Sync collectedFields → manualForm whenever AI updates fields
  useEffect(() => {
    setManualForm(prev => ({
      name:  collectedFields.name  ?? prev.name,
      age:   collectedFields.age   ?? prev.age,
      phone: collectedFields.phone ?? prev.phone,
      blood: collectedFields.blood_group ?? prev.blood,
      city:  collectedFields.city  ?? prev.city,
    }));
  }, [collectedFields]);

  // ── Manual form → sync back to collectedFields ───────────────────────────
  const updateManual = (k: keyof typeof manualForm, v: string) => {
    setManualForm(f => ({ ...f, [k]: v }));
    if (k === 'name') setCollectedFields(c => ({ ...c, name: v || null }));
    if (k === 'age') setCollectedFields(c => ({ ...c, age: v || null }));
    if (k === 'phone') setCollectedFields(c => ({ ...c, phone: v || null }));
    if (k === 'blood') setCollectedFields(c => ({ ...c, blood_group: v || null }));
    if (k === 'city') setCollectedFields(c => ({ ...c, city: v || null }));
  };

  // ── Send typed text to Ollama ─────────────────────────────────────────────
  const handleSendText = async () => {
    if (!textInput.trim() || isProcessing) return;
    const txt = textInput.trim();
    setTextInput('');
    await sendText(txt);
  };

  // ── Final submit ─────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    const name = manualForm.name.trim();
    if (!name) { setFormError(t.errName); return; }
    if (!consent) { setFormError(t.errConsent); return; }

    cancelTTS();
    setLoading(true);

    try {
      const res = await faceApi.post('/register', {
        name,
        age: manualForm.age ? parseInt(manualForm.age) : null,
        phone: manualForm.phone || null,
        gender: selectedGender || 'Unknown',
        blood_group: manualForm.blood || null,
        city: manualForm.city || null,
        embedding: tempEmbedding,
      });

      if (res.data?.status === 'registered') {
        setPatient({
          id: res.data.id,
          name,
          age: manualForm.age ? parseInt(manualForm.age) : undefined,
          gender: selectedGender || undefined,
          phone: manualForm.phone || undefined,
          blood_group: manualForm.blood || undefined,
          city: manualForm.city || undefined,
        });
        speak(`Registration successful. Welcome, ${name.split(' ')[0]}!`, 'en');
        setStep('CONVERSATION');
      }
    } catch (err: any) {
      const msg = err?.response?.data?.message?.en || 'Registration failed. Please try again.';
      setFormError(msg);
    } finally {
      setLoading(false);
    }
  };

  // ── Styles ────────────────────────────────────────────────────────────────
  const inputCls = "w-full p-3 text-base rounded-xl bg-[#F2F6FA] border-2 border-[#DDE4EE] focus:border-[#2E7D96] outline-none transition-all";
  const labelCls = "block text-xs font-semibold text-[#8A9BB5] uppercase tracking-widest mb-1";

  // Chat bubble styles
  const userBubble = "bg-[#2E7D96] text-white px-4 py-2 rounded-2xl rounded-tr-sm max-w-[80%] ml-auto text-sm";
  const aiBubble = "bg-white border border-[#DDE4EE] text-[#1A2B4A] px-4 py-2 rounded-2xl rounded-tl-sm max-w-[80%] text-sm shadow-sm";

  const showGreetingBubble = history.length === 0;

  return (
    <div className="h-full flex flex-col bg-[#F2F6FA] overflow-hidden">
      {/* ── Header ── */}
      <div className="px-5 pt-4 pb-2 flex items-center gap-3 border-b border-[#DDE4EE] bg-white flex-shrink-0">
        <div className="w-10 h-10 rounded-full bg-[#2E7D96] flex items-center justify-center">
          <Bot size={20} className="text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-[#1A2B4A]"
            style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
            {t.title}
          </h1>
          <p className="text-xs text-[#8A9BB5]">{t.subtitle}</p>
        </div>
      </div>

      {/* ── Main content area ── */}
      <div className="flex-1 flex overflow-hidden">

        {/* Left: Chat + Mic */}
        <div className="flex-1 flex flex-col min-w-0">

          {/* Chat history */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {/* Initial AI greeting bubble */}
            {showGreetingBubble && (
              <div className="flex items-start gap-2">
                <div className="w-6 h-6 rounded-full bg-[#2E7D96] flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Bot size={12} className="text-white" />
                </div>
                <p className={aiBubble}>{t.aiGreeting}</p>
              </div>
            )}

            {/* Conversation history */}
            {history.map((msg, i) => (
              <div key={i} className={`flex items-start gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                {msg.role === 'assistant' && (
                  <div className="w-6 h-6 rounded-full bg-[#2E7D96] flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Bot size={12} className="text-white" />
                  </div>
                )}
                <p className={msg.role === 'user' ? userBubble : aiBubble}>
                  {msg.content}
                </p>
              </div>
            ))}

            {/* Processing indicator */}
            {isProcessing && (
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-[#2E7D96] flex items-center justify-center flex-shrink-0">
                  <Bot size={12} className="text-white" />
                </div>
                <div className={`${aiBubble} flex items-center gap-2`}>
                  <Loader2 size={14} className="animate-spin text-[#2E7D96]" />
                  <span>{t.processing}</span>
                </div>
              </div>
            )}

            {/* Voice error */}
            {voiceError && (
              <p className="text-center text-red-500 text-xs">{voiceError}</p>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Text input bar */}
          <div className="px-4 pb-3 flex gap-2 flex-shrink-0 border-t border-[#DDE4EE] pt-3">
            <input
              ref={textInputRef}
              type="text"
              value={textInput}
              onChange={e => setTextInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSendText()}
              placeholder={t.typeHint}
              disabled={isProcessing}
              className="flex-1 px-4 py-2 rounded-xl bg-white border-2 border-[#DDE4EE] focus:border-[#2E7D96] outline-none text-sm disabled:opacity-50"
            />
            <button
              onClick={handleSendText}
              disabled={!textInput.trim() || isProcessing}
              className="p-2 bg-[#2E7D96] text-white rounded-xl disabled:opacity-40 hover:bg-[#236d84] transition-colors"
            >
              <Send size={18} />
            </button>
          </div>

          {/* Mic button (Hands-free VAD) */}
          <div className="pb-4 flex flex-col items-center gap-2 flex-shrink-0">
            <button
              onClick={!isListeningMode ? initListening : undefined}
              disabled={isProcessing || isSpeaking}
              className={`
                w-16 h-16 rounded-full flex items-center justify-center
                transition-all duration-200 shadow-lg select-none relative
                ${isRecording
                  ? 'bg-red-500 scale-110 ring-4 ring-red-300'
                  : isSpeaking
                    ? 'bg-amber-400 cursor-not-allowed'
                  : isProcessing
                    ? 'bg-gray-300 cursor-not-allowed'
                  : !isListeningMode
                    ? 'bg-[#2E7D96] hover:bg-[#236d84] animate-pulse'
                    : 'bg-green-500 hover:bg-green-600'
                }
              `}
            >
              {/* Dynamic volume ring when listening but not yet recording */}
              {isListeningMode && !isRecording && !isProcessing && !isSpeaking && (
                <div
                  className="absolute inset-0 rounded-full border-2 border-green-300 opacity-50"
                  style={{ transform: `scale(${1 + volume / 100})`, transition: 'transform 0.1s' }}
                />
              )}
              {isProcessing
                ? <Loader2 size={28} className="text-white animate-spin" />
                : isRecording
                  ? <MicOff size={28} className="text-white" />
                  : <Mic size={28} className="text-white" />
              }
            </button>
            <span className="text-xs text-[#8A9BB5] font-medium text-center px-4">
              {isSpeaking ? 'AI is speaking… wait' 
               : isProcessing ? t.processing 
               : !isListeningMode ? t.holdSpeak
               : isRecording ? 'Hearing you...'
               : t.releaseStop}
            </span>
          </div>
        </div>

        {/* Right panel: Form */}
        <div className="w-72 border-l border-[#DDE4EE] flex flex-col bg-white overflow-hidden">
          <div className="px-4 py-3 border-b border-[#DDE4EE] flex items-center justify-between">
            <span className="text-xs font-semibold text-[#8A9BB5] uppercase tracking-widest">
              {t.orType}
            </span>
            {allCollected && (
              <span className="flex items-center gap-1 text-xs text-green-600 font-semibold">
                <CheckCircle size={12} /> Ready
              </span>
            )}
          </div>

          <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {/* Name */}
            <div>
              <label className={labelCls}>{t.nameLabel}</label>
              <input
                className={inputCls}
                value={manualForm.name}
                onChange={e => updateManual('name', e.target.value)}
                placeholder={ta ? 'எ.கா. அருண்' : 'e.g. Arun Kumar'}
              />
            </div>

            {/* Age + Phone */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={labelCls}>{t.ageLabel}</label>
                <input
                  className={inputCls}
                  type="number" min="0" max="120"
                  value={manualForm.age}
                  onChange={e => updateManual('age', e.target.value)}
                  placeholder="34"
                />
              </div>
              <div>
                <label className={labelCls}>{t.phoneLabel}</label>
                <input
                  className={inputCls}
                  type="tel"
                  value={manualForm.phone}
                  onChange={e => updateManual('phone', e.target.value.replace(/\D/g, ''))}
                  placeholder="9876543210"
                />
              </div>
            </div>

            {/* Blood + City */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={labelCls}>{t.bloodLabel}</label>
                <select
                  className={inputCls}
                  value={manualForm.blood}
                  onChange={e => updateManual('blood', e.target.value)}
                >
                  <option value="">—</option>
                  {BLOOD_GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls}>{t.cityLabel}</label>
                <input
                  className={inputCls}
                  value={manualForm.city}
                  onChange={e => updateManual('city', e.target.value)}
                  placeholder="Chennai"
                />
              </div>
            </div>

            {/* Gender selector — pre-filled by AI, patient can override */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className={labelCls}>{t.genderLabel}</label>
                {tempGender && (
                  <span className="text-[10px] text-[#8A9BB5] italic">
                    {t.genderDetected}: {tempGender}
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                {(['Male', 'Female', 'Other'] as const).map(g => {
                  const isSelected = selectedGender === g;
                  const isDetected = tempGender === g && !selectedGender;
                  const active     = selectedGender === g || (!selectedGender && tempGender === g);
                  return (
                    <button
                      key={g}
                      type="button"
                      onClick={() => setSelectedGender(g)}
                      className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border-2 transition-all active:scale-95
                        ${ active
                            ? 'bg-[#2E7D96] border-[#2E7D96] text-white shadow-md'
                            : 'bg-[#F2F6FA] border-[#DDE4EE] text-[#4A5C78] hover:border-[#2E7D96]'
                        }`}
                    >
                      {g === 'Male'   ? '♂ Male'   : ''}
                      {g === 'Female' ? '♀ Female' : ''}
                      {g === 'Other'  ? '⚧ Other'  : ''}
                    </button>
                  );
                })}
              </div>
              {!selectedGender && !tempGender && (
                <p className="text-[10px] text-amber-600 mt-1">{t.genderCorrect}</p>
              )}
            </div>

            {/* Consent */}
            <label className="flex items-start gap-2 cursor-pointer bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-3 py-2">
              <input
                type="checkbox"
                checked={consent}
                onChange={e => setConsent(e.target.checked)}
                className="mt-0.5 accent-[#2E7D96] w-4 h-4 flex-shrink-0"
              />
              <span className="text-xs text-[#92400E]"
                style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
                {t.consentLabel}
              </span>
            </label>

            {formError && (
              <p className="text-red-600 text-xs font-medium">{formError}</p>
            )}

            <button
              type="submit"
              disabled={loading || !manualForm.name.trim() || !consent}
              className="w-full bg-[#2E7D96] hover:bg-[#236d84] disabled:opacity-40
                text-white py-3 rounded-xl text-sm font-bold flex items-center
                justify-center gap-2 transition-all active:scale-95"
            >
              {loading
                ? <><Loader2 size={16} className="animate-spin" />{t.submitLoading}</>
                : <><ChevronRight size={16} />{t.submitBtn}</>}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Registration;
