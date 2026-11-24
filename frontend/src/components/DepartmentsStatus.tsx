import React from 'react';
import i18n from '../i18n';
import { Loader2 } from 'lucide-react';
import { useKioskStore } from '../store/useKioskStore';

/** Renders loading / error+retry for the departments list; null when ready. */
const DepartmentsStatus: React.FC = () => {
  const status = useKioskStore((s) => s.departmentsStatus);
  const load = useKioskStore((s) => s.loadDepartments);
  const language = useKioskStore((s) => s.language);
  const t = i18n.getFixedT(language);
  const font = language === 'ta' ? { fontFamily: "'Noto Sans Tamil',sans-serif" } : undefined;

  if (status === 'ready') return null;
  if (status === 'error') {
    return (
      <div className="bg-red-50 border-2 border-red-200 text-red-700 rounded-2xl p-5 text-center my-3" style={font}>
        <p className="font-semibold mb-3">{t('dept_error')}</p>
        <button
          onClick={() => load(true)}
          className="bg-red-600 text-white px-8 py-3 rounded-xl font-bold active:scale-95 transition-all"
        >
          {t('retry')}
        </button>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 text-[#8A9BB5] justify-center py-4" style={font}>
      <Loader2 size={18} className="animate-spin" /> {t('dept_loading')}
    </div>
  );
};

export default DepartmentsStatus;
