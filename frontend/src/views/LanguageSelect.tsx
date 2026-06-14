import React from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { Languages } from 'lucide-react';

const LanguageSelect: React.FC = () => {
  const { setStep, setLanguage } = useKioskStore();
  const { speak } = useTTS();

  const select = (lang: 'en' | 'ta') => {
    setLanguage(lang);
    speak(
      lang === 'ta'
        ? 'தமிழ் தேர்ந்தெடுக்கப்பட்டது. கேமராவை நோக்கி பாருங்கள்.'
        : 'English selected. Please look at the camera.',
      lang
    );
    setTimeout(() => setStep('SCAN'), 800);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-10 bg-[#F2F6FA]">
      <Languages size={56} className="text-[#2E7D96] mb-5" />
      <h1 className="text-4xl font-bold text-[#1A2B4A] mb-2">மொழியைத் தேர்ந்தெடுக்கவும்</h1>
      <p className="text-xl text-[#4A5C78] mb-12">Select Your Language</p>

      <div className="grid grid-cols-2 gap-8 w-full max-w-xl">
        <button
          onClick={() => select('ta')}
          className="bg-white rounded-3xl shadow-lg border-2 border-transparent hover:border-[#2E7D96] active:scale-95 transition-all p-12 flex flex-col items-center gap-4"
        >
          <span className="text-6xl">🇮🇳</span>
          <span className="text-3xl font-bold text-[#1A2B4A]" style={{ fontFamily: "'Noto Sans Tamil', sans-serif" }}>
            தமிழ்
          </span>
        </button>
        <button
          onClick={() => select('en')}
          className="bg-white rounded-3xl shadow-lg border-2 border-transparent hover:border-[#2E7D96] active:scale-95 transition-all p-12 flex flex-col items-center gap-4"
        >
          <span className="text-6xl">🇬🇧</span>
          <span className="text-3xl font-bold text-[#1A2B4A]">English</span>
        </button>
      </div>
    </div>
  );
};

export default LanguageSelect;
