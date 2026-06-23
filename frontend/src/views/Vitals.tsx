import React, { useEffect, useState } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useVoiceField, useTTS } from '../hooks/useVoice';
import VoiceMicBtn from '../components/VoiceMicBtn';
import {
  Activity, ArrowRight, Loader2, ChevronLeft, Check,
  AlertTriangle, Info, TrendingUp, History,
} from 'lucide-react';
import { faceApi } from '../services/api';

const PROMPTS = {
  height: { en: 'Please say your height in centimetres.', ta: 'உயரம் சென்டிமீட்டரில் சொல்லுங்கள்.' },
  weight: { en: 'Please say your weight in kilograms.',   ta: 'எடை கிலோகிராமில் சொல்லுங்கள்.' },
  bp_sys: { en: 'Systolic blood pressure — the top number.', ta: 'மேல் இரத்த அழுத்தம்.' },
  bp_dia: { en: 'Diastolic blood pressure — the bottom number.', ta: 'கீழ் இரத்த அழுத்தம்.' },
  spo2:   { en: 'Oxygen saturation percentage.', ta: 'ஆக்சிஜன் அளவு சதவிகிதம்.' },
};

const L = {
  en: {
    title: 'Medical Vitals', sub: 'Enter or speak your measurements — all optional.',
    height: 'Height', weight: 'Weight', bpSys: 'BP Systolic', bpDia: 'BP Diastolic', spo2: 'SpO₂',
    history: 'Previous History', diabetes: 'Diabetes', hypertension: 'Hypertension',
    skip: 'Skip', next: 'Save & Continue', saving: 'Saving…',
    bmiLabel: 'BMI', flagsLabel: 'Clinical Flags',
    prevVitals: 'Last Visit Vitals', noHistory: 'No previous readings.',
    tts: 'Please enter your vitals. Tap the mic button next to each field to speak.',
  },
  ta: {
    title: 'உடல் அளவீடுகள்', sub: 'அளவீடுகளை உள்ளிடவும் — அனைத்தும் விருப்பத்தேர்வு.',
    height: 'உயரம்', weight: 'எடை', bpSys: 'BP மேல்', bpDia: 'BP கீழ்', spo2: 'ஆக்சிஜன்',
    history: 'முந்தைய வரலாறு', diabetes: 'நீரிழிவு', hypertension: 'உயர் இரத்த அழுத்தம்',
    skip: 'தவிர்', next: 'சேமித்து தொடரவும்', saving: 'சேமிக்கிறது…',
    bmiLabel: 'BMI', flagsLabel: 'மருத்துவ குறிப்புகள்',
    prevVitals: 'கடைசி வருகை அளவீடுகள்', noHistory: 'முந்தைய பதிவுகள் இல்லை.',
    tts: 'உடல் அளவீடுகளை உள்ளிடவும்.',
  },
};

// ── BMI helpers ───────────────────────────────────────────────────────────────
function computeBMI(h: string, w: string): number | null {
  const hN = parseFloat(h), wN = parseFloat(w);
  if (!hN || !wN || hN <= 0) return null;
  return Math.round((wN / ((hN / 100) ** 2)) * 10) / 10;
}

function bmiCategory(bmi: number): { label: string; color: string } {
  if (bmi < 18.5) return { label: 'Underweight', color: 'text-blue-500' };
  if (bmi < 25)   return { label: 'Normal',      color: 'text-green-600' };
  if (bmi < 30)   return { label: 'Overweight',  color: 'text-amber-500' };
  return              { label: 'Obese',         color: 'text-red-500' };
}

function bpCategory(sys: string, dia: string): { label: string; color: string } | null {
  const s = parseInt(sys), d = parseInt(dia);
  if (!s) return null;
  if (s >= 180 || d >= 120) return { label: 'Hypertensive Crisis', color: 'text-red-600' };
  if (s >= 140 || d >= 90)  return { label: 'Stage 2 HTN',         color: 'text-red-500' };
  if (s >= 130 || d >= 80)  return { label: 'Stage 1 HTN',         color: 'text-amber-500' };
  if (s < 90)               return { label: 'Low BP',              color: 'text-blue-500' };
  return { label: 'Normal BP', color: 'text-green-600' };
}

function spo2Category(spo2: string): { label: string; color: string } | null {
  const v = parseFloat(spo2);
  if (!v) return null;
  if (v < 90) return { label: 'Critical — needs O₂', color: 'text-red-600' };
  if (v < 95) return { label: 'Low SpO₂', color: 'text-amber-500' };
  return { label: 'Normal SpO₂', color: 'text-green-600' };
}

// ── Previous vitals card ──────────────────────────────────────────────────────
interface PrevVitals {
  height?: number; weight?: number; bp_sys?: number; bp_dia?: number;
  spo2?: number; diabetes?: boolean; hypertension?: boolean;
  created_at?: string; bmi?: number; flags?: string[];
}

const Vitals: React.FC = () => {
  const { language, patient, vitals, setVitals, setStep } = useKioskStore();
  const { speak } = useTTS();
  const { listenFor, activeField, fieldError } = useVoiceField();
  const [loading, setLoading]   = useState(false);
  const [prevVitals, setPrev]   = useState<PrevVitals | null>(null);
  const [savedFlags, setSavedFlags] = useState<string[]>([]);
  const t  = L[language];
  const ta = language === 'ta';

  // ── Load previous vitals ────────────────────────────────────────────────────
  useEffect(() => {
    speak(t.tts);
    if (patient?.id) {
      faceApi.get(`/vitals/${patient.id}/latest`)
        .then(r => { if (r.data?.vitals) setPrev(r.data.vitals); })
        .catch(() => {});
    }
  }, []);

  const setV = (k: keyof typeof vitals, v: string | boolean) => setVitals({ [k]: v });
  const extractNum = (s: string) => s.replace(/[^0-9.]/g, '');

  // ── Live BMI + flags ────────────────────────────────────────────────────────
  const liveBMI    = computeBMI(vitals.height, vitals.weight);
  const bmiCat     = liveBMI ? bmiCategory(liveBMI) : null;
  const bpCat      = bpCategory(vitals.bp_sys, vitals.bp_dia);
  const spo2Cat    = spo2Category(vitals.spo2);

  // ── Save ────────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!patient?.id) { setStep('CONFIRM'); return; }

    setLoading(true);
    try {
      const res = await faceApi.post('/vitals', {
        patient_id:  patient.id,
        height:      vitals.height      ? parseFloat(vitals.height)  : null,
        weight:      vitals.weight      ? parseFloat(vitals.weight)  : null,
        bp_sys:      vitals.bp_sys      ? parseInt(vitals.bp_sys)    : null,
        bp_dia:      vitals.bp_dia      ? parseInt(vitals.bp_dia)    : null,
        spo2:        vitals.spo2        ? parseFloat(vitals.spo2)    : null,
        diabetes:    vitals.diabetes,
        hypertension: vitals.hypertension,
      });
      if (res.data?.flags?.length) setSavedFlags(res.data.flags);
    } catch (err) {
      console.error('[Vitals] Save failed:', err);
    }
    setLoading(false);
    setStep('CONFIRM');
  };

  // ── Styles ──────────────────────────────────────────────────────────────────
  const inputCls = "flex-1 p-4 text-lg rounded-xl bg-[#F2F6FA] border-2 border-[#DDE4EE] focus:border-[#2E7D96] outline-none transition-all";
  const labelCls = "block text-xs font-semibold text-[#8A9BB5] uppercase tracking-widest mb-2";

  const VField = ({
    fkey, label, unit, placeholder,
  }: { fkey: keyof typeof vitals & string; label: string; unit: string; placeholder: string }) => (
    <div>
      <label className={labelCls}>{label} <span className="normal-case font-normal">({unit})</span></label>
      <div className="flex items-center gap-1">
        <input
          className={inputCls} type="number"
          value={vitals[fkey] as string}
          onChange={e => setV(fkey as any, e.target.value)}
          placeholder={placeholder}
        />
        <VoiceMicBtn
          fieldKey={fkey} activeField={activeField}
          error={activeField == null && fieldError ? fieldError : null}
          onClick={() => listenFor(fkey, PROMPTS[fkey as keyof typeof PROMPTS], v => setV(fkey as any, extractNum(v)))}
        />
      </div>
    </div>
  );

  return (
    <div className="p-6 h-full flex flex-col bg-[#F2F6FA] overflow-y-auto gap-5">

      {/* ── Header ── */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <Activity size={32} className="text-[#2E7D96]" />
          <h1 className="text-3xl font-bold text-[#1A2B4A]"
            style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
            {t.title}
          </h1>
        </div>
        <p className="text-sm text-[#4A5C78]">{t.sub}</p>
      </div>

      {/* ── Previous vitals ── */}
      {prevVitals && (
        <div className="bg-[#E8F4F8] border border-[#B8DDE8] rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <History size={16} className="text-[#2E7D96]" />
            <span className="text-sm font-semibold text-[#2E7D96] uppercase tracking-wider">
              {t.prevVitals}
            </span>
            {prevVitals.created_at && (
              <span className="text-xs text-[#8A9BB5] ml-auto">
                {new Date(prevVitals.created_at).toLocaleDateString('en-IN')}
              </span>
            )}
          </div>
          <div className="grid grid-cols-4 gap-3 text-sm">
            {prevVitals.height   && <div><p className="text-[#8A9BB5] text-xs">Height</p><p className="font-bold text-[#1A2B4A]">{prevVitals.height} cm</p></div>}
            {prevVitals.weight   && <div><p className="text-[#8A9BB5] text-xs">Weight</p><p className="font-bold text-[#1A2B4A]">{prevVitals.weight} kg</p></div>}
            {prevVitals.bmi      && <div><p className="text-[#8A9BB5] text-xs">BMI</p><p className="font-bold text-[#1A2B4A]">{prevVitals.bmi}</p></div>}
            {prevVitals.bp_sys   && <div><p className="text-[#8A9BB5] text-xs">BP</p><p className="font-bold text-[#1A2B4A]">{prevVitals.bp_sys}/{prevVitals.bp_dia}</p></div>}
            {prevVitals.spo2     && <div><p className="text-[#8A9BB5] text-xs">SpO₂</p><p className="font-bold text-[#1A2B4A]">{prevVitals.spo2}%</p></div>}
          </div>
          {prevVitals.flags && prevVitals.flags.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {prevVitals.flags.map(f => (
                <span key={f} className="text-xs bg-amber-100 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full font-medium">
                  {f}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Input form ── */}
      <div className="bg-white rounded-3xl shadow-lg p-6 space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <VField fkey="height" label={t.height} unit="cm" placeholder="170" />
          <VField fkey="weight" label={t.weight} unit="kg" placeholder="65" />
        </div>

        {/* Live BMI badge */}
        {liveBMI && bmiCat && (
          <div className="flex items-center gap-3 bg-[#F2F6FA] rounded-2xl px-4 py-3">
            <TrendingUp size={18} className="text-[#2E7D96]" />
            <span className="text-sm font-medium text-[#4A5C78]">{t.bmiLabel}:</span>
            <span className={`text-lg font-black ${bmiCat.color}`}>{liveBMI}</span>
            <span className={`text-sm font-semibold ${bmiCat.color}`}>— {bmiCat.label}</span>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          <VField fkey="bp_sys" label={t.bpSys} unit="mmHg" placeholder="120" />
          <VField fkey="bp_dia" label={t.bpDia} unit="mmHg" placeholder="80"  />
          <VField fkey="spo2"   label={t.spo2}  unit="%"    placeholder="98"  />
        </div>

        {/* Live BP + SpO2 flags */}
        {(bpCat || spo2Cat) && (
          <div className="flex flex-wrap gap-2">
            {bpCat && (
              <span className={`text-xs font-semibold px-3 py-1 rounded-full border
                ${bpCat.color.includes('red') ? 'bg-red-50 border-red-200' :
                  bpCat.color.includes('amber') ? 'bg-amber-50 border-amber-200' :
                  'bg-green-50 border-green-200'} ${bpCat.color}`}>
                {bpCat.label}
              </span>
            )}
            {spo2Cat && (
              <span className={`text-xs font-semibold px-3 py-1 rounded-full border
                ${spo2Cat.color.includes('red') ? 'bg-red-50 border-red-200' :
                  spo2Cat.color.includes('amber') ? 'bg-amber-50 border-amber-200' :
                  'bg-green-50 border-green-200'} ${spo2Cat.color}`}>
                {spo2Cat.label}
              </span>
            )}
          </div>
        )}

        {/* History toggles */}
        <div>
          <label className={labelCls}>{t.history}</label>
          <div className="flex gap-4">
            {(['diabetes', 'hypertension'] as const).map(k => (
              <button key={k} type="button"
                onClick={() => setV(k, !vitals[k])}
                className={`flex-1 flex items-center justify-between p-4 rounded-2xl border-2 transition-all ${
                  vitals[k]
                    ? 'bg-[#E3F2F7] border-[#2E7D96] text-[#1A2B4A]'
                    : 'bg-[#F2F6FA] border-[#DDE4EE] text-[#8A9BB5]'
                }`}>
                <span className="font-semibold"
                  style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
                  {k === 'diabetes' ? t.diabetes : t.hypertension}
                </span>
                <div className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${
                  vitals[k] ? 'bg-[#2E7D96]' : 'bg-[#DDE4EE]'}`}>
                  {vitals[k] && <Check size={16} className="text-white" />}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── DB save note ── */}
      <div className="flex items-start gap-2 bg-blue-50 border border-blue-200 rounded-2xl px-4 py-3">
        <Info size={16} className="text-blue-400 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-blue-600 font-medium">
          Vitals are saved to your patient record in the hospital database and linked to your Patient ID #{patient?.id}.
        </p>
      </div>

      {/* ── Actions ── */}
      <div className="flex gap-4">
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
            ? <><Loader2 size={22} className="animate-spin" />{t.saving}</>
            : <><ArrowRight size={22} />{t.next}</>}
        </button>
      </div>
    </div>
  );
};

export default Vitals;
