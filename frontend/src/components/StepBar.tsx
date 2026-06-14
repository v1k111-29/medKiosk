import React from 'react';
import { useKioskStore, KioskStep } from '../store/useKioskStore';

const STEPS: { key: KioskStep[]; label: string; labelTa: string }[] = [
  { key: ['SCAN'],                       label: 'Identify',   labelTa: 'அடையாளம்' },
  { key: ['REGISTER'],                   label: 'Register',   labelTa: 'பதிவு' },
  { key: ['MENU'],                       label: 'Service',    labelTa: 'சேவை' },
  { key: ['TRIAGE', 'DEPARTMENT'],       label: 'Dept',       labelTa: 'துறை' },
  { key: ['VITALS'],                     label: 'Vitals',     labelTa: 'உடல் தரவு' },
  { key: ['CONFIRM'],                    label: 'Ticket',     labelTa: 'டிக்கெட்' },
];

const StepBar: React.FC = () => {
  const { step, language } = useKioskStore();
  const activeIdx = STEPS.findIndex(s => s.key.includes(step));
  if (activeIdx < 0) return null;

  return (
    <div className="flex items-center justify-center gap-0 px-6 py-3 bg-white border-b border-[#DDE4EE]">
      {STEPS.map((s, i) => {
        const done   = i < activeIdx;
        const active = i === activeIdx;
        return (
          <React.Fragment key={i}>
            <div className={`flex items-center gap-2 px-3 transition-all ${active ? 'opacity-100' : done ? 'opacity-60' : 'opacity-30'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 transition-all ${
                done   ? 'bg-[#1F7A5C] text-white' :
                active ? 'bg-[#2E7D96] text-white ring-4 ring-[#E3F2F7]' :
                         'bg-[#DDE4EE] text-[#8A9BB5]'
              }`}>
                {done ? '✓' : i + 1}
              </div>
              <div className="hidden sm:block">
                <div className={`text-xs font-semibold leading-tight ${active ? 'text-[#1A2B4A]' : 'text-[#8A9BB5]'}`}
                  style={{ fontFamily: language === 'ta' ? "'Noto Sans Tamil', sans-serif" : undefined }}>
                  {language === 'ta' ? s.labelTa : s.label}
                </div>
              </div>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-px max-w-[40px] ${i < activeIdx ? 'bg-[#1F7A5C]' : 'bg-[#DDE4EE]'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

export default StepBar;
