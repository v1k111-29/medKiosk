/**
 * Shown whenever the SERVER decides urgency is "emergency" (red flags / NEWS2 / AI).
 * The appointment is already booked into the emergency queue, which alerts staff
 * through the queue websocket. If booking failed, the patient is told to find staff.
 */
import React, { useEffect } from 'react';
import { useKioskStore, findDepartment } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import i18n from '../i18n';
import { Bilingual, Disclaimer } from '../components/Bilingual';
import { Siren } from 'lucide-react';

const AUTO_RESET_MS = 90_000;

const EmergencyAlert: React.FC = () => {
  const { language, booking, departments, reset } = useKioskStore();
  const { speakBoth } = useTTS();
  const er = findDepartment(departments, 'emergency');
  const room = booking?.room || er?.room || 'ER-1';
  const booked = !!booking;

  useEffect(() => {
    const en = i18n.getFixedT('en');
    const ta = i18n.getFixedT('ta');
    const staffKey = booked ? 'emergency_staff' : 'emergency_tell_staff';
    speakBoth(`${en('emergency_title', { room })}. ${en(staffKey)}`, `${ta('emergency_title', { room })}. ${ta(staffKey)}`);
    const timer = setTimeout(() => reset(), AUTO_RESET_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div role="alert" aria-live="assertive"
      className="h-full w-full flex flex-col items-center justify-center p-8 text-center bg-[#B91C1C] text-white overflow-y-auto">
      <Siren size={96} className="mb-6 animate-pulse" />
      <h1 className="mb-6 max-w-4xl">
        <Bilingual k="emergency_title" lang={language} vars={{ room }}
          primaryClass="text-5xl md:text-6xl font-black leading-tight"
          secondaryClass="text-3xl md:text-4xl font-bold mt-3 opacity-95" />
      </h1>

      <div className="bg-white/15 border-2 border-white/40 rounded-3xl px-8 py-5 mb-6">
        <Bilingual k={booked ? 'emergency_staff' : 'emergency_tell_staff'} lang={language}
          primaryClass="text-3xl font-bold" secondaryClass="text-2xl font-semibold opacity-90" />
      </div>

      {booking && (
        <div className="bg-white text-[#B91C1C] rounded-3xl px-10 py-4 mb-6 shadow-2xl">
          <Bilingual k="emergency_token" lang={language} primaryClass="text-sm font-black uppercase tracking-widest"
            secondaryClass="text-xs font-bold" />
          <p className="text-7xl font-black tabular-nums leading-none mt-1">{booking.token}</p>
        </div>
      )}

      <p className="mb-6">
        <Bilingual k="emergency_help" lang={language} primaryClass="text-xl font-semibold" secondaryClass="text-lg opacity-90" />
      </p>

      <Disclaimer lang={language} className="mb-6 max-w-xl" />

      <button onClick={reset}
        className="bg-white text-[#B91C1C] px-16 py-5 rounded-2xl text-3xl font-black shadow-xl active:scale-95 transition-all">
        <Bilingual k="emergency_ok" lang={language} primaryClass="" secondaryClass="text-lg font-bold" />
      </button>
    </div>
  );
};

export default EmergencyAlert;
