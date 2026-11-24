/**
 * Face-data consent. Shown before any camera capture whose result could be stored.
 * "I agree" -> SCAN (face template may be saved on registration).
 * "No"      -> PHONE (identify by mobile number + OTP; nothing face-related is kept).
 */
import React, { useEffect } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import i18n from '../i18n';
import { Bilingual } from '../components/Bilingual';
import { ScanFace, Smartphone, ShieldCheck, Trash2, Hash, Heart } from 'lucide-react';

const POINTS = [
  { k: 'consent_point_template', icon: Hash },
  { k: 'consent_point_use', icon: ScanFace },
  { k: 'consent_point_delete', icon: Trash2 },
  { k: 'consent_point_optout', icon: Heart },
] as const;

const Consent: React.FC = () => {
  const { language, setStep, setFaceConsent, setTempEmbedding, setTempGender, reset } = useKioskStore();
  const { speakBoth } = useTTS();

  useEffect(() => {
    speakBoth(i18n.getFixedT('en')('consent_title'), i18n.getFixedT('ta')('consent_title'));
  }, [speakBoth]);

  const agree = () => {
    setFaceConsent(true);
    setStep('SCAN');
  };

  const decline = () => {
    setFaceConsent(false);
    setTempEmbedding(null);
    setTempGender(null);
    setStep('PHONE');
  };

  return (
    <div className="h-full flex flex-col items-center justify-center p-8 bg-[#F2F6FA] overflow-y-auto">
      <ShieldCheck size={56} className="text-[#2E7D96] mb-4" />
      <h1 className="text-center mb-6 max-w-3xl">
        <Bilingual k="consent_title" lang={language}
          primaryClass="text-3xl md:text-4xl font-black text-[#1A2B4A] leading-tight"
          secondaryClass="text-xl md:text-2xl font-semibold text-[#4A5C78] mt-2" />
      </h1>

      <ul className="bg-white rounded-3xl shadow-lg p-6 w-full max-w-3xl space-y-4 mb-8">
        {POINTS.map(({ k, icon: Icon }) => (
          <li key={k} className="flex items-start gap-4">
            <Icon size={28} className="text-[#2E7D96] flex-shrink-0 mt-1" />
            <span>
              <Bilingual k={k} lang={language}
                primaryClass="text-lg font-semibold text-[#1A2B4A]" secondaryClass="text-base text-[#4A5C78]" />
            </span>
          </li>
        ))}
      </ul>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full max-w-3xl">
        <button
          onClick={agree}
          className="flex items-center gap-4 bg-[#1F7A5C] hover:bg-[#186349] text-white rounded-3xl p-6 shadow-xl
            active:scale-95 transition-all text-left min-h-[120px]"
        >
          <ScanFace size={44} className="flex-shrink-0" />
          <span>
            <Bilingual k="consent_agree" lang={language}
              primaryClass="text-2xl font-black" secondaryClass="text-lg font-semibold opacity-90" />
          </span>
        </button>
        <button
          onClick={decline}
          className="flex items-center gap-4 bg-white border-4 border-[#2E7D96] text-[#1A2B4A] rounded-3xl p-6 shadow-xl
            active:scale-95 transition-all text-left min-h-[120px]"
        >
          <Smartphone size={44} className="flex-shrink-0 text-[#2E7D96]" />
          <span>
            <Bilingual k="consent_decline" lang={language}
              primaryClass="text-2xl font-black" secondaryClass="text-lg font-semibold text-[#4A5C78]" />
          </span>
        </button>
      </div>

      <button onClick={reset} className="mt-6 text-[#8A9BB5] font-semibold text-lg">
        <Bilingual k="cancel" lang={language} primaryClass="" secondaryClass="text-sm" />
      </button>
    </div>
  );
};

export default Consent;
