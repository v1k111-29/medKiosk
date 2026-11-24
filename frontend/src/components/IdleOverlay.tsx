import React from 'react';
import i18n from '../i18n';
import { useKioskStore } from '../store/useKioskStore';
import { useIdleReset } from '../hooks/useIdleReset';

const IdleOverlay: React.FC = () => {
  const { remaining, dismiss } = useIdleReset();
  const language = useKioskStore((s) => s.language);
  if (remaining === null) return null;

  const t = i18n.getFixedT(language);
  const font = language === 'ta' ? { fontFamily: "'Noto Sans Tamil',sans-serif" } : undefined;
  // Always show both languages: this screen may appear on any language setting.
  const other = i18n.getFixedT(language === 'ta' ? 'en' : 'ta');

  return (
    <div
      role="alertdialog"
      aria-live="assertive"
      className="fixed inset-0 z-[100] bg-[#1A2B4A]/90 flex items-center justify-center p-8"
      onClick={dismiss}
    >
      <div className="bg-white rounded-3xl shadow-2xl p-10 max-w-xl w-full text-center">
        <h1 className="text-4xl font-black text-[#1A2B4A] mb-2" style={font}>{t('idle_title')}</h1>
        <p className="text-xl text-[#4A5C78] mb-6">{other('idle_title')}</p>
        <p className="text-8xl font-black text-[#2E7D96] tabular-nums mb-4">{remaining}</p>
        <p className="text-lg text-[#4A5C78]" style={font}>{t('idle_sub', { n: remaining })}</p>
        <p className="text-base text-[#8A9BB5] mb-8">{other('idle_sub', { n: remaining })}</p>
        <button
          onClick={dismiss}
          className="w-full bg-[#2E7D96] hover:bg-[#236d84] text-white py-5 rounded-2xl text-2xl font-bold active:scale-95 transition-all"
        >
          <span style={font}>{t('idle_continue')}</span>
          <span className="block text-base font-medium opacity-80">{other('idle_continue')}</span>
        </button>
      </div>
    </div>
  );
};

export default IdleOverlay;
