import React, { useEffect } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { Stethoscope, Calendar, RefreshCw, LogOut, ChevronRight } from 'lucide-react';

const L = {
  en: {
    greeting: (n: string) => `Welcome back, ${n}`,
    meta: (g: string, a: number|undefined, v: number|undefined) =>
      `${g}${a ? ` · Age ${a}` : ''} · Visits: ${v ?? 1}`,
    cards: [
      { key: 'symptoms',    icon: Stethoscope, label: 'Visit for Symptoms',  sub: 'Describe & get a token',    color: '#2E7D96', border: '#2E7D96' },
      { key: 'appointment', icon: Calendar,    label: 'Book Appointment',     sub: 'Schedule a future visit',   color: '#1F7A5C', border: '#1F7A5C' },
      { key: 'followup',    icon: RefreshCw,   label: 'Follow-up Visit',      sub: 'Continue ongoing treatment',color: '#7B5EA7', border: '#7B5EA7' },
    ],
    logout: 'Exit',
    tts: (n: string) => `Welcome back, ${n}. Please choose a service.`,
  },
  ta: {
    greeting: (n: string) => `மீண்டும் வருக, ${n}`,
    meta: (g: string, a: number|undefined, v: number|undefined) =>
      `${g}${a ? ` · வயது ${a}` : ''} · வருகைகள்: ${v ?? 1}`,
    cards: [
      { key: 'symptoms',    icon: Stethoscope, label: 'அறிகுறி ஆலோசனை',   sub: 'அறிகுறிகளை விவரித்து டோக்கன் பெறவும்', color: '#2E7D96', border: '#2E7D96' },
      { key: 'appointment', icon: Calendar,    label: 'சந்திப்பு பதிவு',    sub: 'எதிர்கால ஆலோசனை திட்டமிடவும்',        color: '#1F7A5C', border: '#1F7A5C' },
      { key: 'followup',    icon: RefreshCw,   label: 'மறு சந்திப்பு',      sub: 'நடந்து வரும் சிகிச்சையை தொடரவும்',    color: '#7B5EA7', border: '#7B5EA7' },
    ],
    logout: 'வெளியேறு',
    tts: (n: string) => `மீண்டும் வருக, ${n}. சேவையை தேர்ந்தெடுக்கவும்.`,
  },
};

const MainMenu: React.FC = () => {
  const { language, patient, setStep, setTriage, reset } = useKioskStore();
  const { speak } = useTTS();
  const t = L[language];
  const first = patient?.name?.split(' ')[0] || 'Patient';

  useEffect(() => { speak(t.tts(first)); }, []);

  const select = (key: string) => {
    setTriage({ service: key as any });
    speak(language === 'ta' ? 'சரி. துறையை தேர்ந்தெடுக்கவும்.' : 'Got it. Please select a department.');
    if (key === 'symptoms' || key === 'followup') setStep('TRIAGE');
    else setStep('DEPARTMENT');
  };

  const ta = language === 'ta';

  return (
    <div className="p-8 h-full flex flex-col bg-[#F2F6FA]">
      {/* Header */}
      <header className="flex justify-between items-start mb-8">
        <div>
          <h1 className="text-4xl font-black text-[#1A2B4A] leading-tight"
            style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
            {t.greeting(first)}
          </h1>
          <p className="text-base text-[#4A5C78] mt-1">
            {t.meta(patient?.gender||'', patient?.age, patient?.visits)}
          </p>
        </div>
        <button onClick={reset}
          className="flex items-center gap-2 text-[#8A9BB5] hover:text-red-500 font-semibold text-sm transition-colors">
          <LogOut size={18} /> {t.logout}
        </button>
      </header>

      {/* Service cards */}
      <div className="grid grid-cols-1 gap-5 flex-1">
        {t.cards.map(card => (
          <button
            key={card.key}
            onClick={() => select(card.key)}
            className="bg-white rounded-3xl shadow-md border-l-[6px] p-7 flex items-center gap-6
              hover:shadow-xl hover:-translate-y-1 active:scale-98 transition-all text-left"
            style={{ borderColor: card.border }}
          >
            <div className="rounded-2xl p-4 flex-shrink-0" style={{ background: card.color + '18' }}>
              <card.icon size={40} style={{ color: card.color }} />
            </div>
            <div className="flex-1">
              <p className="text-xl font-bold text-[#1A2B4A] leading-tight"
                style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
                {card.label}
              </p>
              <p className="text-sm text-[#4A5C78] mt-1">{card.sub}</p>
            </div>
            <ChevronRight size={24} className="text-[#B8DDE8] flex-shrink-0" />
          </button>
        ))}
      </div>
    </div>
  );
};

export default MainMenu;
