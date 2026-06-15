import React, { useState, useEffect } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useVoiceField, useTTS } from '../hooks/useVoice';
import VoiceMicBtn from '../components/VoiceMicBtn';
import { UserPlus, CheckCircle, Loader2 } from 'lucide-react';
import { faceApi } from '../services/api';

const L = {
  en: {
    title: 'New Patient Registration',
    subName: 'Full Name', subAge: 'Age', subPhone: 'Mobile Number',
    subGender: 'Detected Gender', subBlood: 'Blood Group', subCity: 'City / Town',
    subConsent: 'I consent to my biometric data being stored securely (DPDP Act 2023)',
    btnSubmit: 'Save & Continue', btnLoading: 'Registering…',
    errFill: 'Please fill name and accept consent.',
    prompts: {
      name:   { en: 'Please say your full name.',   ta: 'உங்கள் முழு பெயரை சொல்லுங்கள்.' },
      age:    { en: 'Please say your age.',          ta: 'உங்கள் வயதை சொல்லுங்கள்.' },
      phone:  { en: 'Please say your phone number digit by digit.', ta: 'உங்கள் தொலைபேசி எண்ணை இலக்கம் இலக்கமாக சொல்லுங்கள்.' },
      city:   { en: 'Please say your city or town.', ta: 'உங்கள் ஊரை சொல்லுங்கள்.' },
    },
    tts_intro: 'New patient. Please fill in your details. Each field has a microphone button you can tap to speak.',
  },
  ta: {
    title: 'புதிய நோயாளி பதிவு',
    subName: 'முழு பெயர்', subAge: 'வயது', subPhone: 'மொபைல் எண்',
    subGender: 'கண்டறியப்பட்ட பாலினம்', subBlood: 'இரத்த வகை', subCity: 'ஊர்',
    subConsent: 'என் முக தரவை பாதுகாப்பாக சேமிக்க ஒப்புதல் தருகிறேன் (DPDP சட்டம் 2023)',
    btnSubmit: 'சேமித்து தொடரவும்', btnLoading: 'பதிவு செய்கிறது…',
    errFill: 'பெயர் மற்றும் ஒப்புதல் தேவை.',
    prompts: {
      name:  { en: 'Please say your full name.',   ta: 'உங்கள் முழு பெயரை சொல்லுங்கள்.' },
      age:   { en: 'Please say your age.',          ta: 'உங்கள் வயதை சொல்லுங்கள்.' },
      phone: { en: 'Please say your phone number.', ta: 'உங்கள் தொலைபேசி எண்ணை சொல்லுங்கள்.' },
      city:  { en: 'Please say your city.',         ta: 'உங்கள் ஊரை சொல்லுங்கள்.' },
    },
    tts_intro: 'புதிய நோயாளி. உங்கள் விவரங்களை நிரப்பவும். ஒவ்வொரு புலத்திலும் மைக்ரோஃபோன் பொத்தான் உள்ளது.',
  },
};

const BLOOD_GROUPS = ['A+','A-','B+','B-','O+','O-','AB+','AB-'];

const Registration: React.FC = () => {
  const { language, tempGender, setStep, setPatient } = useKioskStore();
  const { speak } = useTTS();
  const { listenFor, activeField } = useVoiceField();
  const t = L[language];

  const [form, setForm] = useState({ name: '', age: '', phone: '', blood: '', city: '' });
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => { speak(t.tts_intro); }, []);

  const set = (k: keyof typeof form, v: string) => setForm(f => ({ ...f, [k]: v }));

  const wordToNum = (s: string) => {
    const map: Record<string, string> = {
      zero:'0',one:'1',two:'2',three:'3',four:'4',five:'5',
      six:'6',seven:'7',eight:'8',nine:'9',ten:'10',
      eleven:'11',twelve:'12',thirteen:'13',fourteen:'14',fifteen:'15',
      sixteen:'16',seventeen:'17',eighteen:'18',nineteen:'19',twenty:'20',
    };
    const clean = s.toLowerCase().trim();
    return map[clean] ?? s.replace(/\D/g, '');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !consent) { setErr(t.errFill); return; }
    const { tempEmbedding } = useKioskStore.getState();
    setLoading(true);
    try {
      const res = await faceApi.post('/register', {
        name: form.name, 
        age: form.age ? parseInt(form.age) : null,
        phone: form.phone, 
        gender: tempGender,
        blood_group: form.blood, 
        city: form.city,
        embedding: tempEmbedding,
      });
      const data = res.data;
      if (data.status === 'registered') {
        setPatient({ id: data.id, name: form.name, age: parseInt(form.age)||0, gender: tempGender||'', phone: form.phone });
        speak(language === 'ta'
          ? `பதிவு வெற்றிகரமாக முடிந்தது. நல்வரவு, ${form.name.split(' ')[0]}!`
          : `Registration successful. Welcome, ${form.name.split(' ')[0]}!`
        );
        setStep(language === 'en' ? 'CONVERSATION' : 'MENU');
      }
    } catch { setErr('Registration failed. Please try again.'); }
    finally { setLoading(false); }
  };

  const inputCls = "w-full p-4 text-lg rounded-xl bg-[#F2F6FA] border-2 border-[#DDE4EE] focus:border-[#2E7D96] outline-none transition-all";
  const labelCls = "block text-xs font-semibold text-[#8A9BB5] uppercase tracking-widest mb-2";
  const ta = language === 'ta';

  return (
    <div className="h-full overflow-y-auto p-6 bg-[#F2F6FA]">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <UserPlus size={36} className="text-[#2E7D96]" />
          <h1 className="text-3xl font-bold text-[#1A2B4A]"
            style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
            {t.title}
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-3xl shadow-lg p-8 space-y-5">
          <div>
            <label className={labelCls}>{t.subName} *</label>
            <div className="flex items-center">
              <input className={inputCls} value={form.name}
                onChange={e => set('name', e.target.value)}
                placeholder={ta ? 'எ.கா. அருண் குமார்' : 'e.g. Arun Kumar'} />
              <VoiceMicBtn fieldKey="name" activeField={activeField}
                onClick={() => listenFor('name', t.prompts.name, v => set('name', v))} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>{t.subAge}</label>
              <div className="flex items-center">
                <input className={inputCls} type="number" value={form.age}
                  onChange={e => set('age', e.target.value)} placeholder="e.g. 34" min="0" max="120" />
                <VoiceMicBtn fieldKey="age" activeField={activeField}
                  onClick={() => listenFor('age', t.prompts.age, v => set('age', wordToNum(v)))} />
              </div>
            </div>
            <div>
              <label className={labelCls}>{t.subPhone}</label>
              <div className="flex items-center">
                <input className={inputCls} type="tel" value={form.phone}
                  onChange={e => set('phone', e.target.value)} placeholder="98765 43210" />
                <VoiceMicBtn fieldKey="phone" activeField={activeField}
                  onClick={() => listenFor('phone', t.prompts.phone, v => set('phone', v.replace(/\D/g,'')))} />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>{t.subBlood}</label>
              <select className={inputCls} value={form.blood} onChange={e => set('blood', e.target.value)}>
                <option value="">Select</option>
                {BLOOD_GROUPS.map(g => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>{t.subCity}</label>
              <div className="flex items-center">
                <input className={inputCls} value={form.city}
                  onChange={e => set('city', e.target.value)} placeholder="Coimbatore" />
                <VoiceMicBtn fieldKey="city" activeField={activeField}
                  onClick={() => listenFor('city', t.prompts.city, v => set('city', v))} />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 bg-[#E3F2F7] border border-[#B8DDE8] rounded-xl px-4 py-3">
            <CheckCircle size={18} className="text-[#2E7D96]" />
            <span className="text-sm font-medium text-[#1A2B4A]">
              {t.subGender}: <strong>{tempGender || '—'}</strong>
            </span>
          </div>

          <label className="flex items-start gap-3 cursor-pointer bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-4 py-3">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)}
              className="mt-1 accent-[#2E7D96] w-4 h-4 flex-shrink-0" />
            <span className="text-sm text-[#92400E]">{t.subConsent}</span>
          </label>

          {err && <p className="text-red-600 text-sm font-medium">{err}</p>}

          <button type="submit" disabled={loading}
            className="w-full bg-[#2E7D96] hover:bg-[#236d84] disabled:opacity-50 text-white
              py-5 rounded-2xl text-lg font-bold flex items-center justify-center gap-3 transition-all active:scale-95">
            {loading
              ? <><Loader2 size={20} className="animate-spin" />{t.btnLoading}</>
              : <><UserPlus size={20} />{t.btnSubmit}</>}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Registration;
