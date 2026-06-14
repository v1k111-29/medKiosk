import React, { useEffect, useState } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { Printer, CheckCircle, RotateCcw } from 'lucide-react';

const L = {
  en: {
    checkedIn: "You're Checked In!",
    smsSent: 'A confirmation SMS has been sent to your mobile.',
    smsNone: 'No mobile number on file.',
    tokenLabel: 'Token Number',
    dept: 'Department', room: 'Room', patient: 'Patient',
    service: 'Service', waitTime: 'Est. Wait', immediate: 'Immediate',
    printBtn: 'Print Ticket', doneBtn: 'Finish',
    serviceLbl: { symptoms: 'Symptoms', appointment: 'Appointment', followup: 'Follow-up', emergency: 'Emergency' },
    tts: (t: string, d: string, r: string, w: string) =>
      `You are checked in. Your token is ${t}. Department: ${d}. Room: ${r}. Estimated wait: ${w} minutes.`,
  },
  ta: {
    checkedIn: 'நீங்கள் உள்நுழைந்துவிட்டீர்கள்!',
    smsSent: 'உங்கள் மொபைலுக்கு உறுதிப்படுத்தல் SMS அனுப்பப்பட்டது.',
    smsNone: 'மொபைல் எண் பதிவு இல்லை.',
    tokenLabel: 'டோக்கன் எண்',
    dept: 'துறை', room: 'அறை', patient: 'நோயாளி',
    service: 'சேவை', waitTime: 'காத்திரு நேரம்', immediate: 'உடனடி',
    printBtn: 'டிக்கெட் அச்சிடு', doneBtn: 'முடிக்கவும்',
    serviceLbl: { symptoms: 'அறிகுறி', appointment: 'சந்திப்பு', followup: 'மறு சந்திப்பு', emergency: 'அவசரம்' },
    tts: (t: string, d: string, r: string, w: string) =>
      `நீங்கள் உள்நுழைந்தீர்கள். டோக்கன் ${t}. துறை: ${d}. அறை: ${r}. காத்திரு நேரம்: ${w} நிமிடங்கள்.`,
  },
};

function genToken() {
  const prefix = ['A','B','C','D'][Math.floor(Math.random() * 4)];
  return `${prefix}-${String(Math.floor(Math.random() * 98) + 1).padStart(2,'0')}`;
}

const Confirmation: React.FC = () => {
  const { language, patient, triage, token, setToken, reset } = useKioskStore();
  const { speak } = useTTS();
  const t = L[language];
  const ta = language === 'ta';
  const [smsSent, setSmsSent] = useState(false);

  useEffect(() => {
    const tok = genToken();
    setToken(tok);

    const dept = ta ? triage.deptNameTa : triage.deptName;
    const wait = triage.waitMins > 0 ? String(triage.waitMins) : t.immediate;
    speak(t.tts(tok, dept, triage.room, wait));

    // simulate SMS
    if (patient?.phone) {
      setTimeout(() => {
        console.log(`[SMS] To: ${patient.phone} — Token ${tok}, ${triage.deptName}, ${triage.room}`);
        setSmsSent(true);
      }, 1500);
    }

    // auto-reset after 45 s
    const timer = setTimeout(() => reset(), 45000);
    return () => clearTimeout(timer);
  }, []);

  const handlePrint = () => {
    window.print();
    setTimeout(() => reset(), 6000);
  };

  const svcLbl = triage.service
    ? t.serviceLbl[triage.service as keyof typeof t.serviceLbl] ?? triage.service
    : '—';

  const deptName = ta ? triage.deptNameTa : triage.deptName;
  const waitLabel = triage.waitMins > 0 ? `~${triage.waitMins} min` : t.immediate;

  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-6 bg-[#F2F6FA]">

      {/* Success icon */}
      <div className="relative mb-5">
        <CheckCircle size={80} className="text-[#1F7A5C]" />
        <div className="absolute inset-0 animate-ping rounded-full border-4 border-[#1F7A5C] opacity-20 pointer-events-none" />
      </div>

      <h1 className="text-4xl font-black text-[#1A2B4A] mb-2"
        style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
        {t.checkedIn}
      </h1>

      <p className={`text-base mb-6 ${smsSent ? 'text-[#1F7A5C]' : 'text-[#8A9BB5]'}`}>
        {patient?.phone ? (smsSent ? `📱 ${t.smsSent}` : '📱 Sending SMS…') : t.smsNone}
      </p>

      {/* Ticket card */}
      <div id="ticket-print"
        className="bg-white rounded-3xl shadow-2xl border-t-8 border-[#2E7D96] w-full max-w-sm overflow-hidden">

        {/* Token */}
        <div className="px-8 pt-8 pb-4 text-center">
          <p className="text-xs font-black text-[#8A9BB5] uppercase tracking-[0.25em] mb-1"
            style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
            {t.tokenLabel}
          </p>
          <p className="text-8xl font-black text-[#1A2B4A] leading-none tabular-nums">{token || '—'}</p>
        </div>

        {/* Dept badge */}
        <div className="mx-8 mb-4">
          <div className="bg-[#E3F2F7] border border-[#B8DDE8] rounded-2xl px-4 py-3 text-center">
            <p className="text-lg font-bold text-[#2E7D96]"
              style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
              {deptName || '—'}
            </p>
          </div>
        </div>

        {/* Dashed divider */}
        <div className="border-t-2 border-dashed border-[#DDE4EE] mx-6 mb-4" />

        {/* Meta rows */}
        <div className="px-8 pb-6 space-y-2 text-sm">
          {[
            [t.patient,  patient?.name || '—'],
            [t.service,  svcLbl],
            [t.room,     triage.room || '—'],
            [t.waitTime, waitLabel],
          ].map(([lbl, val]) => (
            <div key={lbl} className="flex justify-between items-center">
              <span className="text-[#8A9BB5] font-medium"
                style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>{lbl}</span>
              <span className="font-bold text-[#1A2B4A]">{val}</span>
            </div>
          ))}
        </div>

        {/* Timestamp footer */}
        <div className="bg-[#F2F6FA] px-8 py-3 border-t border-[#DDE4EE] text-center">
          <p className="text-xs text-[#8A9BB5]">
            {new Date().toLocaleString('en-IN', { dateStyle:'medium', timeStyle:'short' })}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-4 mt-6 w-full max-w-sm">
        <button onClick={handlePrint}
          className="flex-1 flex items-center justify-center gap-3 bg-[#F59E0B] hover:bg-[#D97706]
            text-white py-4 rounded-2xl text-base font-bold shadow-lg active:scale-95 transition-all">
          <Printer size={20} />
          <span style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>{t.printBtn}</span>
        </button>
        <button onClick={reset}
          className="flex items-center justify-center gap-2 bg-white border-2 border-[#DDE4EE]
            text-[#4A5C78] hover:border-[#2E7D96] px-6 py-4 rounded-2xl font-semibold transition-all">
          <RotateCcw size={20} />
          <span style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>{t.doneBtn}</span>
        </button>
      </div>

      {/* Print-only styles injected */}
      <style>{`
        @media print {
          body > * { display: none !important; }
          #ticket-print { display: block !important; position: fixed; top: 0; left: 0;
            width: 80mm; border-radius: 0; box-shadow: none; border: none; }
        }
      `}</style>
    </div>
  );
};

export default Confirmation;
