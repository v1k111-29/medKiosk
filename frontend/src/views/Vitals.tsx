import React, { useEffect, useState } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useVoiceField, useTTS } from '../hooks/useVoice';
import VoiceMicBtn from '../components/VoiceMicBtn';
import { Activity, ArrowRight, Loader2, ChevronLeft, Check } from 'lucide-react';
import { faceApi } from '../services/api';

const PROMPTS = {
  height:  { en: 'Please say your height in centimeters.', ta: 'உங்கள் உயரத்தை சென்டிமீட்டரில் சொல்லுங்கள்.' },
  weight:  { en: 'Please say your weight in kilograms.',   ta: 'உங்கள் எடையை கிலோகிராமில் சொல்லுங்கள்.' },
  bp_sys:  { en: 'Please say your systolic blood pressure.', ta: 'மேல் இரத்த அழுத்தம் சொல்லுங்கள்.' },
  bp_dia:  { en: 'Please say your diastolic blood pressure.', ta: 'கீழ் இரத்த அழுத்தம் சொல்லுங்கள்.' },
  spo2:    { en: 'Please say your oxygen saturation percentage.', ta: 'ஆக்சிஜன் அளவை சொல்லுங்கள்.' },
};

const L = {
  en: {
    title: 'Medical Vitals',
    sub: 'Please enter or speak your measurements. All fields are optional.',
    height: 'Height', weight: 'Weight', bpSys: 'BP Systolic', bpDia: 'BP Diastolic', spo2: 'SpO₂',
    history: 'Previous Medical History',
    diabetes: 'Diabetes', hypertension: 'Hypertension',
    skip: 'Skip', next: 'Save & Continue',
    tts: 'Please enter your vitals. Each field has a microphone button you can tap to speak.',
  },
  ta: {
    title: 'உடல் அளவீடுகள்',
    sub: 'உங்கள் அளவீடுகளை உள்ளிடவும் அல்லது பேசவும். அனைத்தும் விருப்பத்தேர்வு.',
    height: 'உயரம்', weight: 'எடை', bpSys: 'BP மேல்', bpDia: 'BP கீழ்', spo2: 'ஆக்சிஜன்',
    history: 'முந்தைய மருத்துவ வரலாறு',
    diabetes: 'நீரிழிவு', hypertension: 'உயர் இரத்த அழுத்தம்',
    skip: 'தவிர்', next: 'சேமித்து தொடரவும்',
    tts: 'உங்கள் உடல் அளவீடுகளை உள்ளிடவும். ஒவ்வொரு புலத்திலும் மைக்ரோஃபோன் பொத்தான் உள்ளது.',
  },
};

const Vitals: React.FC = () => {
  const { language, patient, vitals, setVitals, setStep } = useKioskStore();
  const { speak } = useTTS();
  const { listenFor, activeField } = useVoiceField();
  const [loading, setLoading] = useState(false);
  const t = L[language];
  const ta = language === 'ta';

  useEffect(() => { speak(t.tts); }, []);

  const setV = (k: keyof typeof vitals, v: string | boolean) =>
    setVitals({ [k]: v });

  const extractNum = (s: string) => s.replace(/[^0-9.]/g, '');

  const handleSave = async () => {
    if (patient?.id) {
      setLoading(true);
      try {
        await faceApi.post('/vitals', {
          patient_id: patient.id,
          height:     vitals.height  ? parseInt(vitals.height)  : null,
          weight:     vitals.weight  ? parseInt(vitals.weight)  : null,
          bp_sys:     vitals.bp_sys  ? parseInt(vitals.bp_sys)  : null,
          bp_dia:     vitals.bp_dia  ? parseInt(vitals.bp_dia)  : null,
          spo2:       vitals.spo2    ? parseInt(vitals.spo2)    : null,
          diabetes:   vitals.diabetes,
          hypertension: vitals.hypertension,
        });
      } catch { /* non-critical */ }
      setLoading(false);
    }
    setStep('CONFIRM');
  };

  const inputCls = "flex-1 p-4 text-lg rounded-xl bg-[#F2F6FA] border-2 border-[#DDE4EE] focus:border-[#2E7D96] outline-none transition-all";
  const labelCls = "block text-xs font-semibold text-[#8A9BB5] uppercase tracking-widest mb-2";

  const VField = ({ fkey, label, unit, placeholder }: { fkey: keyof typeof vitals & string; label: string; unit: string; placeholder: string }) => (
    <div>
      <label className={labelCls}>{label} <span className="normal-case font-normal">({unit})</span></label>
      <div className="flex items-center gap-1">
        <input className={inputCls} type="number"
          value={vitals[fkey] as string}
          onChange={e => setV(fkey as any, e.target.value)}
          placeholder={placeholder} />
        <VoiceMicBtn fieldKey={fkey} activeField={activeField}
          onClick={() => listenFor(fkey, PROMPTS[fkey as keyof typeof PROMPTS], v => setV(fkey as any, extractNum(v)))} />
      </div>
    </div>
  );

  return (
    <div className="p-6 h-full flex flex-col bg-[#F2F6FA] overflow-y-auto">
      <div className="flex items-center gap-3 mb-1">
        <Activity size={32} className="text-[#2E7D96]" />
        <h1 className="text-3xl font-bold text-[#1A2B4A]"
          style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
          {t.title}
        </h1>
      </div>
      <p className="text-sm text-[#4A5C78] mb-5">{t.sub}</p>

      <div className="bg-white rounded-3xl shadow-lg p-6 space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <VField fkey="height" label={t.height} unit="cm" placeholder="170" />
          <VField fkey="weight" label={t.weight} unit="kg" placeholder="65" />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <VField fkey="bp_sys"  label={t.bpSys} unit="mmHg" placeholder="120" />
          <VField fkey="bp_dia"  label={t.bpDia} unit="mmHg" placeholder="80"  />
          <VField fkey="spo2"    label={t.spo2}  unit="%"    placeholder="98"  />
        </div>

        <div>
          <label className={labelCls}>{t.history}</label>
          <div className="flex gap-4">
            {(['diabetes','hypertension'] as const).map(k => (
              <button key={k} type="button"
                onClick={() => setV(k, !vitals[k])}
                className={`flex-1 flex items-center justify-between p-4 rounded-2xl border-2 transition-all ${
                  vitals[k]
                    ? 'bg-[#E3F2F7] border-[#2E7D96] text-[#1A2B4A]'
                    : 'bg-[#F2F6FA] border-[#DDE4EE] text-[#8A9BB5]'
                }`}>
                <span className="font-semibold" style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
                  {k === 'diabetes' ? t.diabetes : t.hypertension}
                </span>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${
                  vitals[k] ? 'bg-[#2E7D96]' : 'bg-[#DDE4EE]'
                }`}>
                  {vitals[k] && <Check size={16} className="text-white" />}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-4 mt-5">
        <button onClick={() => setStep('MENU')}
          className="flex items-center gap-2 bg-white border-2 border-[#DDE4EE] text-[#4A5C78]
            px-6 py-4 rounded-2xl font-semibold hover:border-[#2E7D96] transition-all">
          <ChevronLeft size={20} /> {t.skip}
        </button>
        <button onClick={handleSave} disabled={loading}
          className="flex-1 bg-[#2E7D96] hover:bg-[#236d84] disabled:opacity-50 text-white
            py-4 rounded-2xl text-lg font-bold flex items-center justify-center gap-3
            shadow-lg active:scale-95 transition-all">
          {loading
            ? <><Loader2 size={22} className="animate-spin" />Saving…</>
            : <><ArrowRight size={22} />{t.next}</>}
        </button>
      </div>
    </div>
  );
};

export default Vitals;
