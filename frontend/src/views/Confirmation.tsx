import React, { useEffect, useRef, useState } from 'react';
import i18n from '../i18n';
import { useKioskStore, deptLabel, findDepartment } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { faceApi, bookAppointment, errorDetail, BookingResult } from '../services/api';
import { maskPhone } from '../utils';
import DepartmentsStatus from '../components/DepartmentsStatus';
import { Printer, CheckCircle, RotateCcw, Activity, Loader2, MessageSquare } from 'lucide-react';

interface VitalsSummary {
  height?: number | null;
  weight?: number | null;
  bmi?: number | null;
  bp_sys?: number | null;
  bp_dia?: number | null;
  spo2?: number | null;
  flags?: string[];
}

const L = {
  en: {
    checkedIn: "You're Checked In!",
    tokenLabel: 'Token Number',
    dept: 'Department', room: 'Room', patient: 'Patient',
    service: 'Service', waitTime: 'Est. Wait', immediate: 'Immediate',
    minutes: (n: number) => `${n} minutes`,
    printBtn: 'Print Ticket', doneBtn: 'Finish',
    serviceLbl: { symptoms: 'Symptoms', appointment: 'Appointment', followup: 'Follow-up', emergency: 'Emergency' },
    tts: (t: string, d: string, r: string, w: string) =>
      `You are checked in. Your token is ${t}. Department: ${d}. Room: ${r}. Estimated wait: ${w}.`,
  },
  ta: {
    checkedIn: 'நீங்கள் உள்நுழைந்துவிட்டீர்கள்!',
    tokenLabel: 'டோக்கன் எண்',
    dept: 'துறை', room: 'அறை', patient: 'நோயாளி',
    service: 'சேவை', waitTime: 'காத்திரு நேரம்', immediate: 'உடனடி',
    minutes: (n: number) => `${n} நிமிடங்கள்`,
    printBtn: 'டிக்கெட் அச்சிடு', doneBtn: 'முடிக்கவும்',
    serviceLbl: { symptoms: 'அறிகுறி', appointment: 'சந்திப்பு', followup: 'மறு சந்திப்பு', emergency: 'அவசரம்' },
    tts: (t: string, d: string, r: string, w: string) =>
      `நீங்கள் உள்நுழைந்தீர்கள். டோக்கன் ${t}. துறை: ${d}. அறை: ${r}. காத்திரு நேரம்: ${w}.`,
  },
};

const Confirmation: React.FC = () => {
  const {
    language, patient, triage, booking, setBooking, smsOptIn, setSmsOptIn,
    departments, departmentsStatus, reset,
  } = useKioskStore();
  const { speak } = useTTS();
  const t = L[language];
  const tr = i18n.getFixedT(language);
  const en = i18n.getFixedT('en');
  const taT = i18n.getFixedT('ta');
  const ta = language === 'ta';
  const font = ta ? { fontFamily: "'Noto Sans Tamil',sans-serif" } : undefined;
  const [vitalsData, setVitalsData] = useState<VitalsSummary | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [bookError, setBookError] = useState<string | null>(null);

  const dept = findDepartment(departments, triage.deptId);
  const phone = patient?.phone ?? '';
  const hasPhone = phone.replace(/\D/g, '').length >= 4;

  const waitText = (b: BookingResult) =>
    b.wait_mins > 0 ? t.minutes(b.wait_mins) : t.immediate;

  // Fetch latest vitals to show on slip
  useEffect(() => {
    if (patient?.id) {
      faceApi.get<{ vitals?: VitalsSummary }>(`/vitals/${patient.id}/latest`)
        .then(r => { if (r.data?.vitals) setVitalsData(r.data.vitals); })
        .catch(() => {});
    }
  }, [patient?.id]);

  // Once the server has issued a token: announce it and auto-reset after 45 s.
  const announcedRef = useRef(false);
  useEffect(() => {
    if (!booking || announcedRef.current) return;
    announcedRef.current = true;
    const d = findDepartment(departments, booking.dept_id);
    speak(t.tts(booking.token, d ? deptLabel(d, language) : booking.dept_name, booking.room, waitText(booking)));
    const timer = setTimeout(() => reset(), 45000);
    return () => clearTimeout(timer);
  }, [booking]);

  const submitBooking = async () => {
    if (!patient?.id || !triage.deptId || submitting) return;
    setSubmitting(true);
    setBookError(null);
    try {
      const res = await bookAppointment({
        patient_id: patient.id,
        dept_id: triage.deptId,
        symptoms: triage.symptoms || null,
        service: triage.service ?? 'symptoms',
        urgency: triage.urgency,
        sms_opt_in: hasPhone && smsOptIn,
        doctor_id: triage.doctorId,
        doctor_name: triage.doctorName || null,
      });
      setBooking(res);
    } catch (err) {
      setBookError(errorDetail(err, tr('booking_failed')));
    } finally {
      setSubmitting(false);
    }
  };

  const handlePrint = () => {
    window.print();
    setTimeout(() => reset(), 6000);
  };

  // ── Phase 1: review + SMS opt-in + book (server issues the token) ──
  if (!booking) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-6 bg-[#F2F6FA]">
        <h1 className="text-4xl font-black text-[#1A2B4A] mb-2" style={font}>{tr('review_title')}</h1>
        <p className="text-base text-[#4A5C78] mb-6" style={font}>{tr('review_sub')}</p>

        <div className="bg-white rounded-3xl shadow-xl border-t-8 border-[#2E7D96] w-full max-w-md p-6 mb-5 space-y-3 text-left">
          {departmentsStatus !== 'ready' ? <DepartmentsStatus /> : (
            <>
              <div className="flex justify-between"><span className="text-[#8A9BB5]" style={font}>{t.patient}</span><span className="font-bold text-[#1A2B4A]">{patient?.name || '—'}</span></div>
              <div className="flex justify-between"><span className="text-[#8A9BB5]" style={font}>{t.dept}</span><span className="font-bold text-[#1A2B4A]" style={font}>{deptLabel(dept, language) || '—'}</span></div>
              <div className="flex justify-between"><span className="text-[#8A9BB5]" style={font}>{t.room}</span><span className="font-bold text-[#1A2B4A]">{dept?.room || '—'}</span></div>
              {triage.doctorName && (
                <div className="flex justify-between"><span className="text-[#8A9BB5]">Doctor</span><span className="font-bold text-[#1A2B4A]">{triage.doctorName}</span></div>
              )}
            </>
          )}
        </div>

        {hasPhone && (
          <button
            type="button"
            role="switch"
            aria-checked={smsOptIn}
            onClick={() => setSmsOptIn(!smsOptIn)}
            className={`w-full max-w-md flex items-center gap-4 p-5 rounded-3xl border-4 text-left mb-5 transition-all active:scale-95
              ${smsOptIn ? 'bg-[#E8F5E9] border-[#1F7A5C]' : 'bg-white border-[#DDE4EE]'}`}
          >
            <MessageSquare size={36} className={`flex-shrink-0 ${smsOptIn ? 'text-[#1F7A5C]' : 'text-[#8A9BB5]'}`} />
            <span className="flex-1">
              <span className="block text-xl font-bold text-[#1A2B4A]">{en('sms_toggle', { phone: maskPhone(phone) })}</span>
              <span className="block text-lg font-semibold text-[#4A5C78]" style={{ fontFamily: "'Noto Sans Tamil',sans-serif" }}>
                {taT('sms_toggle', { phone: maskPhone(phone) })}
              </span>
            </span>
            <span className={`w-20 h-11 rounded-full p-1 flex-shrink-0 transition-all ${smsOptIn ? 'bg-[#1F7A5C]' : 'bg-[#C5CFDD]'}`}>
              <span className={`block w-9 h-9 rounded-full bg-white shadow transition-all ${smsOptIn ? 'translate-x-9' : ''}`} />
            </span>
            <span className="sr-only">{smsOptIn ? tr('sms_on') : tr('sms_off')}</span>
          </button>
        )}

        {bookError && (
          <p className="mb-4 bg-red-50 border-2 border-red-200 text-red-700 rounded-2xl px-5 py-3 font-medium" style={font}>
            {bookError}
          </p>
        )}

        <button
          onClick={submitBooking}
          disabled={submitting || !dept || !patient?.id}
          className="w-full max-w-md bg-[#2E7D96] hover:bg-[#236d84] disabled:opacity-40 text-white py-5 rounded-2xl
            text-2xl font-bold flex items-center justify-center gap-3 shadow-lg active:scale-95 transition-all"
          style={font}
        >
          {submitting ? <><Loader2 className="animate-spin" /> {tr('booking_in_progress')}</> : tr('get_token')}
        </button>
        <button onClick={reset} className="mt-4 text-[#8A9BB5] font-semibold" style={font}>{t.doneBtn}</button>
      </div>
    );
  }

  // ── Phase 2: server-issued ticket ──
  const svcKey = (booking.service || triage.service || '') as keyof typeof t.serviceLbl;
  const svcLbl = t.serviceLbl[svcKey] ?? (booking.service || '—');

  const bookedDept = findDepartment(departments, booking.dept_id);
  const deptName = bookedDept ? deptLabel(bookedDept, language) : booking.dept_name;
  const waitLabel = booking.wait_mins > 0 ? `~${booking.wait_mins} min` : t.immediate;
  // Soft status: show only on success; failures are silent.
  const smsSent = booking.sms_status === 'sent' || booking.sms_status === 'mocked';

  const rows: Array<[string, string]> = [
    [t.patient, patient?.name || '—'],
    [t.service, svcLbl],
    ...(booking.doctor_name ? [['Doctor', booking.doctor_name] as [string, string]] : []),
    [t.room, booking.room],
    [tr('queue_position'), String(booking.queue_position)],
    [t.waitTime, waitLabel],
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-6 bg-[#F2F6FA]">

      {/* Success icon */}
      <div className="relative mb-5">
        <CheckCircle size={80} className="text-[#1F7A5C]" />
        <div className="absolute inset-0 animate-ping rounded-full border-4 border-[#1F7A5C] opacity-20 pointer-events-none" />
      </div>

      <h1 className="text-4xl font-black text-[#1A2B4A] mb-2" style={font}>
        {t.checkedIn}
      </h1>

      <p className="text-base mb-6 h-6 text-[#1F7A5C]" style={font}>
        {smsSent ? `📱 ${tr('sms_sent_ok')}` : ''}
      </p>

      {/* Ticket card */}
      <div id="ticket-print"
        className="bg-white rounded-3xl shadow-2xl border-t-8 border-[#2E7D96] w-full max-w-sm overflow-hidden">

        {/* Token */}
        <div className="px-8 pt-8 pb-4 text-center">
          <p className="text-xs font-black text-[#8A9BB5] uppercase tracking-[0.25em] mb-1" style={font}>
            {t.tokenLabel}
          </p>
          <p className="text-8xl font-black text-[#1A2B4A] leading-none tabular-nums">{booking.token}</p>
        </div>

        {/* Dept badge */}
        <div className="mx-8 mb-4">
          <div className="bg-[#E3F2F7] border border-[#B8DDE8] rounded-2xl px-4 py-3 text-center">
            <p className="text-lg font-bold text-[#2E7D96]" style={font}>
              {deptName || '—'}
            </p>
          </div>
        </div>

        {/* Dashed divider */}
        <div className="border-t-2 border-dashed border-[#DDE4EE] mx-6 mb-4" />

        {/* Vitals summary (if available) */}
        {vitalsData && (
          <div className="mx-6 mb-4">
            <div className="flex items-center gap-2 mb-2">
              <Activity size={14} className="text-[#2E7D96]" />
              <span className="text-xs font-bold text-[#8A9BB5] uppercase tracking-wider">Vitals</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              {vitalsData.height && (
                <div className="text-center"><p className="text-[#8A9BB5]">Ht</p><p className="font-bold text-[#1A2B4A]">{vitalsData.height}cm</p></div>
              )}
              {vitalsData.weight && (
                <div className="text-center"><p className="text-[#8A9BB5]">Wt</p><p className="font-bold text-[#1A2B4A]">{vitalsData.weight}kg</p></div>
              )}
              {vitalsData.bmi && (
                <div className="text-center"><p className="text-[#8A9BB5]">BMI</p><p className="font-bold text-[#1A2B4A]">{vitalsData.bmi}</p></div>
              )}
              {vitalsData.bp_sys && (
                <div className="text-center"><p className="text-[#8A9BB5]">BP</p><p className="font-bold text-[#1A2B4A]">{vitalsData.bp_sys}/{vitalsData.bp_dia}</p></div>
              )}
              {vitalsData.spo2 && (
                <div className="text-center"><p className="text-[#8A9BB5]">SpO₂</p><p className="font-bold text-[#1A2B4A]">{vitalsData.spo2}%</p></div>
              )}
            </div>
            {vitalsData.flags && vitalsData.flags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {vitalsData.flags.map((f) => (
                  <span key={f} className="text-xs bg-amber-100 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full font-semibold">
                    ⚠ {f}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Dashed divider 2 */}
        <div className="border-t-2 border-dashed border-[#DDE4EE] mx-6 mb-4" />

        {/* Meta rows */}
        <div className="px-8 pb-6 space-y-2 text-sm">
          {rows.map(([lbl, val]) => (
            <div key={lbl} className="flex justify-between items-center">
              <span className="text-[#8A9BB5] font-medium" style={font}>{lbl}</span>
              <span className="font-bold text-[#1A2B4A]">{val}</span>
            </div>
          ))}
        </div>

        {/* Timestamp footer */}
        <div className="bg-[#F2F6FA] px-8 py-3 border-t border-[#DDE4EE] text-center">
          <p className="text-xs text-[#8A9BB5]">
            {new Date(booking.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-4 mt-6 w-full max-w-sm">
        <button onClick={handlePrint}
          className="flex-1 flex items-center justify-center gap-3 bg-[#F59E0B] hover:bg-[#D97706]
            text-white py-4 rounded-2xl text-base font-bold shadow-lg active:scale-95 transition-all">
          <Printer size={20} />
          <span style={font}>{t.printBtn}</span>
        </button>
        <button onClick={reset}
          className="flex items-center justify-center gap-2 bg-white border-2 border-[#DDE4EE]
            text-[#4A5C78] hover:border-[#2E7D96] px-6 py-4 rounded-2xl font-semibold transition-all">
          <RotateCcw size={20} />
          <span style={font}>{t.doneBtn}</span>
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
