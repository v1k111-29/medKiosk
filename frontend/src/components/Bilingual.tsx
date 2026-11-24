import React from 'react';
import i18n from '../i18n';

const TA_FONT = { fontFamily: "'Noto Sans Tamil',sans-serif" };

/**
 * Shows an i18n key in both languages: the selected language first (large),
 * the other below (smaller). Safety and consent screens must be readable by
 * every visitor regardless of the language toggle.
 */
export const Bilingual: React.FC<{
  k: string;
  lang: 'en' | 'ta';
  vars?: Record<string, unknown>;
  primaryClass?: string;
  secondaryClass?: string;
}> = ({ k, lang, vars, primaryClass = '', secondaryClass = '' }) => {
  const other = lang === 'ta' ? 'en' : 'ta';
  return (
    <>
      <span className={`block ${primaryClass}`} style={lang === 'ta' ? TA_FONT : undefined}>
        {i18n.getFixedT(lang)(k, vars)}
      </span>
      <span className={`block ${secondaryClass}`} style={other === 'ta' ? TA_FONT : undefined}>
        {i18n.getFixedT(other)(k, vars)}
      </span>
    </>
  );
};

/** Short "This is not a diagnosis" notice in both languages. */
export const Disclaimer: React.FC<{ lang: 'en' | 'ta'; className?: string }> = ({ lang, className = '' }) => (
  <div role="note" className={`bg-amber-50 border-2 border-amber-200 rounded-2xl px-4 py-2 text-center ${className}`}>
    <Bilingual k="disclaimer" lang={lang}
      primaryClass="text-sm font-bold text-amber-800" secondaryClass="text-xs font-medium text-amber-700" />
  </div>
);

export default Bilingual;
