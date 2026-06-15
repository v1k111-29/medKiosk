import React, { useEffect } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { DEPARTMENTS, DepartmentData } from '../data/departments';
import { ChevronRight, ChevronLeft, CheckCircle } from 'lucide-react';

const L = {
  en: {
    title: 'Recommended Department',
    subAuto: 'Based on your symptoms, we suggest:',
    subManual: 'Or choose a different department:',
    confirm: 'Confirm & Continue',
    back: 'Back',
    tts: (d: string) => `Based on your symptoms, we recommend ${d}. Tap confirm to continue or choose another department.`,
  },
  ta: {
    title: 'பரிந்துரைக்கப்பட்ட துறை',
    subAuto: 'உங்கள் அறிகுறிகளின் படி பரிந்துரை:',
    subManual: 'அல்லது வேறு துறையை தேர்ந்தெடுக்கவும்:',
    confirm: 'உறுதிப்படுத்தி தொடரவும்',
    back: 'திரும்பு',
    tts: (d: string) => `உங்கள் அறிகுறிகளின் படி ${d} பரிந்துரைக்கப்படுகிறது. உறுதிப்படுத்த தட்டவும்.`,
  },
};

const Department: React.FC = () => {
  const { language, triage, setTriage, setStep } = useKioskStore();
  const { speak } = useTTS();
  const t = L[language];
  const ta = language === 'ta';

  const recommended = DEPARTMENTS.find((d: DepartmentData) => d.id === triage.deptId) ?? DEPARTMENTS[0];
  const selected = DEPARTMENTS.find((d: DepartmentData) => d.id === triage.deptId) ?? DEPARTMENTS[0];

  useEffect(() => {
    speak(t.tts(ta ? recommended.ta : recommended.en));
  }, []);

  const selectDept = (dept: DepartmentData) => {
    setTriage({
      deptId: dept.id,
      deptName: dept.en,
      deptNameTa: dept.ta,
      room: dept.room,
      waitMins: dept.waitMins,
    });
  };

  const confirm = () => {
    speak(language === 'ta'
      ? `${selected.ta}, ${selected.room}. தயவுசெய்து காத்திருங்கள்.`
      : `${selected.en}, ${selected.room}. Please proceed.`
    );
    setStep('VITALS');
  };

  return (
    <div className="p-6 h-full flex flex-col bg-[#F2F6FA] overflow-y-auto">
      <h1 className="text-3xl font-bold text-[#1A2B4A] mb-1"
        style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
        {t.title}
      </h1>
      <p className="text-sm text-[#4A5C78] mb-4">{t.subAuto}</p>

      {/* Recommended highlight */}
      <div
        className="bg-white rounded-3xl shadow-lg border-2 p-5 mb-6 flex items-center gap-4 cursor-pointer transition-all"
        style={{ borderColor: recommended.color }}
        onClick={() => selectDept(recommended)}
      >
        <span className="text-4xl">{recommended.icon}</span>
        <div className="flex-1">
          <p className="text-xl font-bold text-[#1A2B4A]"
            style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
            {ta ? recommended.ta : recommended.en}
          </p>
          <p className="text-sm text-[#4A5C78]">{recommended.room} · ~{recommended.waitMins} min wait</p>
        </div>
        {triage.deptId === recommended.id && (
          <CheckCircle size={28} style={{ color: recommended.color }} />
        )}
      </div>

      {/* All departments grid */}
      <p className="text-xs font-semibold text-[#8A9BB5] uppercase tracking-widest mb-3">{t.subManual}</p>
      <div className="grid grid-cols-2 gap-3 flex-1">
        {DEPARTMENTS.filter((d: DepartmentData) => d.id !== 'emergency').map((dept: DepartmentData) => (
          <button
            key={dept.id}
            onClick={() => selectDept(dept)}
            className={`bg-white rounded-2xl border-2 p-4 flex items-center gap-3 text-left
              transition-all hover:shadow-md active:scale-95 ${
                triage.deptId === dept.id
                  ? 'shadow-lg'
                  : 'border-[#DDE4EE] hover:border-gray-300'
              }`}
            style={triage.deptId === dept.id ? { borderColor: dept.color } : {}}
          >
            <span className="text-2xl flex-shrink-0">{dept.icon}</span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[#1A2B4A] truncate"
                style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
                {ta ? dept.ta : dept.en}
              </p>
              <p className="text-xs text-[#8A9BB5]">{dept.room}</p>
            </div>
            {triage.deptId === dept.id && (
              <CheckCircle size={16} className="ml-auto flex-shrink-0" style={{ color: dept.color }} />
            )}
          </button>
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-4 mt-5">
        <button onClick={() => setStep('TRIAGE')}
          className="flex items-center gap-2 bg-white border-2 border-[#DDE4EE] text-[#4A5C78]
            px-6 py-4 rounded-2xl font-semibold hover:border-[#2E7D96] transition-all">
          <ChevronLeft size={20} /> {t.back}
        </button>
        <button onClick={confirm}
          className="flex-1 bg-[#2E7D96] hover:bg-[#236d84] text-white py-4 rounded-2xl
            text-lg font-bold flex items-center justify-center gap-3 shadow-lg active:scale-95 transition-all">
          <ChevronRight size={22} /> {t.confirm}
        </button>
      </div>
    </div>
  );
};

export default Department;
