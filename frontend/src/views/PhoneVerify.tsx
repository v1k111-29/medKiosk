/**
 * Phone identification for visitors who declined face recognition.
 *
 * 1. Enter 10-digit mobile on a large keypad -> POST /identify/phone/start
 *    (server always answers "otp_sent", so this screen never reveals whether a number is registered)
 * 2. Enter 6-digit code -> POST /identify/phone/verify
 *    found -> (pick a person if several share the number) -> continue as returning patient
 *    new   -> registration without face capture, phone prefilled
 */
import React, { useEffect, useState } from 'react';
import { useKioskStore, Patient } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import i18n from '../i18n';
import { Bilingual } from '../components/Bilingual';
import { phoneStart, phoneVerify, errorDetail, IdentifiedPatient } from '../services/api';
import { Delete, Loader2, Smartphone, KeyRound, UserPlus, User } from 'lucide-react';

type Phase = 'phone' | 'otp' | 'choose';

const PHONE_LEN = 10;
const OTP_LEN = 6;

const Keypad: React.FC<{ onDigit: (d: string) => void; onDelete: () => void; disabled?: boolean; deleteLabel: string }> = ({
  onDigit, onDelete, disabled, deleteLabel,
}) => {
  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'del'];
  return (
    <div className="grid grid-cols-3 gap-3 w-full max-w-sm">
      {keys.map((k, i) => {
        if (!k) return <div key={i} />;
        const isDel = k === 'del';
        return (
          <button
            key={i}
            type="button"
            disabled={disabled}
            aria-label={isDel ? deleteLabel : k}
            onClick={() => (isDel ? onDelete() : onDigit(k))}
            className={`h-20 rounded-2xl text-4xl font-bold shadow-md active:scale-95 transition-all disabled:opacity-40
              ${isDel ? 'bg-[#FDECEC] text-red-600 flex items-center justify-center' : 'bg-white text-[#1A2B4A] border-2 border-[#DDE4EE]'}`}
          >
            {isDel ? <Delete size={34} /> : k}
          </button>
        );
      })}
    </div>
  );
};

const Slots: React.FC<{ value: string; length: number; group?: number[] }> = ({ value, length, group = [] }) => (
  <div className="flex items-center justify-center gap-2 mb-6" aria-live="polite">
    {Array.from({ length }).map((_, i) => (
      <React.Fragment key={i}>
        {group.includes(i) && <span className="w-2" />}
        <span className={`w-10 h-14 md:w-12 md:h-16 rounded-xl border-4 flex items-center justify-center text-3xl font-black tabular-nums
          ${i < value.length ? 'border-[#2E7D96] text-[#1A2B4A] bg-white' : 'border-[#DDE4EE] text-transparent bg-white/60'}`}>
          {value[i] ?? '0'}
        </span>
      </React.Fragment>
    ))}
  </div>
);

const toPatient = (p: IdentifiedPatient): Patient => ({
  id: p.id,
  name: p.name,
  gender: p.gender,
  age: p.age ?? undefined,
  phone: p.phone ?? undefined,
  visits: p.visits ?? undefined,
});

const PhoneVerify: React.FC = () => {
  const { language, setStep, setPatient, setVerifiedPhone, setPhoneVerificationToken, setTempEmbedding, setTempGender, reset } = useKioskStore();
  const { speak } = useTTS();
  const t = i18n.getFixedT(language);
  const [phase, setPhase] = useState<Phase>('phone');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [choices, setChoices] = useState<IdentifiedPatient[]>([]);

  // No face data on this path.
  useEffect(() => {
    setTempEmbedding(null);
    setTempGender(null);
    speak(t('phone_title'));
  }, []);

  const validPhone = /^[6-9]\d{9}$/.test(phone);

  const sendCode = async () => {
    if (!validPhone) { setError(t('phone_invalid')); return; }
    setBusy(true); setError('');
    try {
      await phoneStart(phone);
      setOtp('');
      setPhase('otp');
      speak(t('otp_title', { phone: `******${phone.slice(-4)}` }));
    } catch (err) {
      setError(errorDetail(err, t('phone_error'), language));
    } finally {
      setBusy(false);
    }
  };

  const continueAs = (p: IdentifiedPatient) => {
    setPatient(toPatient(p));
    speak(language === 'ta' ? `வரவேற்கிறோம், ${p.name.split(' ')[0]}!` : `Welcome back, ${p.name.split(' ')[0]}!`);
    setStep(language === 'en' ? 'CONVERSATION' : 'MENU');
  };

  const registerNew = () => {
    setPatient(null);
    setVerifiedPhone(phone);
    setStep('REGISTER');
  };

  const verify = async (code: string) => {
    setBusy(true); setError('');
    try {
      const res = await phoneVerify(phone, code);
      setPhoneVerificationToken(res.phone_verification_token ?? null);
      if (res.status === 'new') {
        registerNew();
        return;
      }
      setVerifiedPhone(phone);
      const all = [res, ...(res.other_patients ?? [])];
      if (all.length > 1) {
        setChoices(all);
        setPhase('choose');
        speak(t('phone_choose'));
      } else {
        continueAs(res);
      }
    } catch (err) {
      setOtp('');
      setError(errorDetail(err, t('phone_error'), language));
    } finally {
      setBusy(false);
    }
  };

  const onDigit = (d: string) => {
    setError('');
    if (phase === 'phone') {
      setPhone((p) => (p.length < PHONE_LEN ? p + d : p));
    } else if (phase === 'otp') {
      setOtp((o) => (o.length < OTP_LEN ? o + d : o));
    }
  };
  // Auto-submit once all 6 digits are entered.
  useEffect(() => {
    if (phase === 'otp' && otp.length === OTP_LEN && !busy) void verify(otp);
  }, [otp, phase]);

  const onDelete = () => {
    setError('');
    if (phase === 'phone') setPhone((p) => p.slice(0, -1));
    else setOtp((o) => o.slice(0, -1));
  };

  return (
    <div className="h-full flex flex-col items-center justify-center p-6 bg-[#F2F6FA] overflow-y-auto">
      {phase === 'choose' ? (
        <>
          <User size={52} className="text-[#2E7D96] mb-3" />
          <h1 className="text-center mb-6">
            <Bilingual k="phone_choose" lang={language}
              primaryClass="text-3xl font-black text-[#1A2B4A]" secondaryClass="text-xl text-[#4A5C78]" />
          </h1>
          <div className="w-full max-w-lg space-y-3">
            {choices.map((p) => (
              <button key={p.id} onClick={() => continueAs(p)}
                className="w-full bg-white border-2 border-[#DDE4EE] hover:border-[#2E7D96] rounded-2xl p-5 text-left shadow-md active:scale-95 transition-all">
                <span className="block text-2xl font-bold text-[#1A2B4A]">{p.name}</span>
                <span className="block text-base text-[#4A5C78]">
                  {[p.gender, p.age ? `${p.age}` : null].filter(Boolean).join(' · ')}
                </span>
              </button>
            ))}
            <button onClick={registerNew}
              className="w-full flex items-center gap-3 bg-[#E3F2F7] border-2 border-[#2E7D96] rounded-2xl p-5 text-left active:scale-95 transition-all">
              <UserPlus size={28} className="text-[#2E7D96]" />
              <span><Bilingual k="phone_someone_else" lang={language}
                primaryClass="text-xl font-bold text-[#1A2B4A]" secondaryClass="text-sm text-[#4A5C78]" /></span>
            </button>
          </div>
        </>
      ) : (
        <>
          {phase === 'phone'
            ? <Smartphone size={52} className="text-[#2E7D96] mb-3" />
            : <KeyRound size={52} className="text-[#2E7D96] mb-3" />}
          <h1 className="text-center mb-2">
            {phase === 'phone' ? (
              <Bilingual k="phone_title" lang={language}
                primaryClass="text-3xl font-black text-[#1A2B4A]" secondaryClass="text-xl text-[#4A5C78]" />
            ) : (
              <Bilingual k="otp_title" lang={language} vars={{ phone: `******${phone.slice(-4)}` }}
                primaryClass="text-3xl font-black text-[#1A2B4A]" secondaryClass="text-xl text-[#4A5C78]" />
            )}
          </h1>
          {phase === 'phone' && (
            <p className="text-center mb-4">
              <Bilingual k="phone_sub" lang={language} primaryClass="text-base text-[#4A5C78]" secondaryClass="text-sm text-[#8A9BB5]" />
            </p>
          )}

          {phase === 'phone'
            ? <Slots value={phone} length={PHONE_LEN} group={[5]} />
            : <Slots value={otp} length={OTP_LEN} group={[3]} />}

          {error && (
            <p role="alert" className="mb-4 bg-red-50 border-2 border-red-200 text-red-700 rounded-2xl px-5 py-3 font-semibold text-center max-w-md"
              style={language === 'ta' ? { fontFamily: "'Noto Sans Tamil',sans-serif" } : undefined}>
              {error}
            </p>
          )}

          <Keypad onDigit={onDigit} onDelete={onDelete} disabled={busy} deleteLabel={t('keypad_delete')} />

          <div className="flex flex-col items-center gap-3 mt-6 w-full max-w-sm">
            {phase === 'phone' ? (
              <button onClick={sendCode} disabled={busy || !validPhone}
                className="w-full bg-[#2E7D96] hover:bg-[#236d84] disabled:opacity-40 text-white py-5 rounded-2xl text-2xl font-bold
                  shadow-lg active:scale-95 transition-all flex items-center justify-center gap-3">
                {busy ? <Loader2 className="animate-spin" /> : null}
                <span><Bilingual k="phone_send" lang={language} primaryClass="" secondaryClass="text-base font-medium opacity-90" /></span>
              </button>
            ) : (
              <>
                <button onClick={() => verify(otp)} disabled={busy || otp.length !== OTP_LEN}
                  className="w-full bg-[#2E7D96] hover:bg-[#236d84] disabled:opacity-40 text-white py-5 rounded-2xl text-2xl font-bold
                    shadow-lg active:scale-95 transition-all flex items-center justify-center gap-3">
                  {busy ? <Loader2 className="animate-spin" /> : null}
                  <span><Bilingual k="otp_verify" lang={language} primaryClass="" secondaryClass="text-base font-medium opacity-90" /></span>
                </button>
                <div className="flex gap-6">
                  <button onClick={sendCode} disabled={busy} className="text-[#2E7D96] font-semibold underline underline-offset-4">
                    {t('otp_resend')}
                  </button>
                  <button onClick={() => { setPhase('phone'); setOtp(''); setError(''); }} disabled={busy}
                    className="text-[#4A5C78] font-semibold underline underline-offset-4">
                    {t('otp_change')}
                  </button>
                </div>
              </>
            )}
            <button onClick={reset} className="text-[#8A9BB5] font-semibold">{t('cancel')}</button>
          </div>
        </>
      )}
    </div>
  );
};

export default PhoneVerify;
