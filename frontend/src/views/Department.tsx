import React, { useEffect, useState } from 'react';
import { useKioskStore } from '../store/useKioskStore';
import { useTTS } from '../hooks/useVoice';
import { DEPARTMENTS, DepartmentData } from '../data/departments';
import { faceApi } from '../services/api';
import { ChevronRight, ChevronLeft, CheckCircle, Loader2, User, Stethoscope } from 'lucide-react';

interface Doctor {
  id: number;
  name: string;
  dept_id: string;
  dept_name: string;
  qualification: string;
  available: boolean;
  room: string;
}

const L = {
  en: {
    title: 'Recommended Department',
    subAuto: 'Based on your symptoms, we suggest:',
    subManual: 'Or choose a different department:',
    confirm: 'Confirm & Continue',
    back: 'Back',
    selectDoctor: 'Select a Doctor',
    noPreference: 'No preference (any available doctor)',
    loading: 'Loading doctors…',
    noDoctors: 'No doctors available right now.',
    unavailable: 'Unavailable',
    tts: (d: string) => `Based on your symptoms, we recommend ${d}. Tap confirm to continue or choose another department.`,
  },
  ta: {
    title: 'பரிந்துரைக்கப்பட்ட துறை',
    subAuto: 'உங்கள் அறிகுறிகளின் படி பரிந்துரை:',
    subManual: 'அல்லது வேறு துறையை தேர்ந்தெடுக்கவும்:',
    confirm: 'உறுதிப்படுத்தி தொடரவும்',
    back: 'திரும்பு',
    selectDoctor: 'மருத்துவரை தேர்வு செய்யவும்',
    noPreference: 'முன்னுரிமை இல்லை (யாரேனும் மருத்துவர்)',
    loading: 'மருத்துவர்கள் ஏற்றப்படுகிறது…',
    noDoctors: 'இப்போது மருத்துவர்கள் இல்லை.',
    unavailable: 'கிடைக்கவில்லை',
    tts: (d: string) => `உங்கள் அறிகுறிகளின் படி ${d} பரிந்துரைக்கப்படுகிறது. உறுதிப்படுத்த தட்டவும்.`,
  },
};

const Department: React.FC = () => {
  const { language, triage, setTriage, setStep } = useKioskStore();
  const { speak } = useTTS();
  const t = L[language];
  const ta = language === 'ta';

  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  const recommended = DEPARTMENTS.find((d: DepartmentData) => d.id === triage.deptId) ?? DEPARTMENTS[0];
  const selected = DEPARTMENTS.find((d: DepartmentData) => d.id === triage.deptId) ?? DEPARTMENTS[0];

  useEffect(() => {
    speak(t.tts(ta ? recommended.ta : recommended.en));
  }, []);

  // Fetch doctors whenever the selected department changes
  useEffect(() => {
    if (!triage.deptId) return;
    setLoadingDocs(true);
    // Reset doctor selection when dept changes
    setTriage({ doctorId: null, doctorName: '' });
    faceApi.get(`/doctors?dept_id=${triage.deptId}`)
      .then(r => {
        const docs = (r.data?.doctors || []) as Doctor[];
        setDoctors(docs);
      })
      .catch(() => setDoctors([]))
      .finally(() => setLoadingDocs(false));
  }, [triage.deptId]);

  const selectDept = (dept: DepartmentData) => {
    setTriage({
      deptId: dept.id,
      deptName: dept.en,
      deptNameTa: dept.ta,
      room: dept.room,
      waitMins: dept.waitMins,
    });
  };

  const selectDoctor = (doc: Doctor | null) => {
    if (doc) {
      setTriage({ doctorId: doc.id, doctorName: doc.name });
    } else {
      setTriage({ doctorId: null, doctorName: '' });
    }
  };

  const confirm = () => {
    const docMsg = triage.doctorName ? `, with ${triage.doctorName}` : '';
    speak(language === 'ta'
      ? `${selected.ta}, ${selected.room}. தயவுசெய்து காத்திருங்கள்.`
      : `${selected.en}, ${selected.room}${docMsg}. Please proceed.`
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
        className="bg-white rounded-3xl shadow-lg border-2 p-5 mb-4 flex items-center gap-4 cursor-pointer transition-all"
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

      {/* ── Doctor Picker ── */}
      <div className="bg-white rounded-3xl shadow-md border border-[#DDE4EE] p-5 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Stethoscope size={18} className="text-[#2E7D96]" />
          <h2 className="text-sm font-bold text-[#1A2B4A] uppercase tracking-wider"
            style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
            {t.selectDoctor}
          </h2>
        </div>

        {loadingDocs ? (
          <div className="flex items-center gap-2 text-[#8A9BB5] text-sm py-4 justify-center">
            <Loader2 size={16} className="animate-spin" /> {t.loading}
          </div>
        ) : doctors.length === 0 ? (
          <p className="text-sm text-[#8A9BB5] text-center py-4">{t.noDoctors}</p>
        ) : (
          <div className="space-y-2">
            {/* No preference option */}
            <button
              onClick={() => selectDoctor(null)}
              className={`w-full flex items-center gap-3 p-3 rounded-2xl border-2 transition-all text-left
                ${!triage.doctorId
                  ? 'bg-[#E3F2F7] border-[#2E7D96] shadow-sm'
                  : 'bg-[#F2F6FA] border-[#DDE4EE] hover:border-[#2E7D96]'
                }`}
            >
              <div className="w-10 h-10 rounded-full bg-[#DDE4EE] flex items-center justify-center flex-shrink-0">
                <User size={18} className="text-[#8A9BB5]" />
              </div>
              <span className="text-sm font-medium text-[#4A5C78]"
                style={{ fontFamily: ta ? "'Noto Sans Tamil',sans-serif" : undefined }}>
                {t.noPreference}
              </span>
              {!triage.doctorId && <CheckCircle size={16} className="ml-auto text-[#2E7D96]" />}
            </button>

            {/* Doctor cards */}
            {doctors.map(doc => {
              const isSelected = triage.doctorId === doc.id;
              const isAvail = doc.available;
              return (
                <button
                  key={doc.id}
                  onClick={() => isAvail && selectDoctor(doc)}
                  disabled={!isAvail}
                  className={`w-full flex items-center gap-3 p-3 rounded-2xl border-2 transition-all text-left
                    ${!isAvail
                      ? 'bg-gray-50 border-gray-200 opacity-60 cursor-not-allowed'
                      : isSelected
                        ? 'bg-[#E3F2F7] border-[#2E7D96] shadow-sm'
                        : 'bg-white border-[#DDE4EE] hover:border-[#2E7D96]'
                    }`}
                >
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0
                    ${isSelected ? 'bg-[#2E7D96]' : 'bg-[#E3F2F7]'}`}>
                    <Stethoscope size={18} className={isSelected ? 'text-white' : 'text-[#2E7D96]'} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-[#1A2B4A] truncate">{doc.name}</p>
                    <p className="text-xs text-[#8A9BB5]">{doc.qualification}</p>
                  </div>
                  {!isAvail ? (
                    <span className="text-xs font-semibold text-red-400 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full">
                      {t.unavailable}
                    </span>
                  ) : isSelected ? (
                    <CheckCircle size={16} className="text-[#2E7D96] flex-shrink-0" />
                  ) : null}
                </button>
              );
            })}
          </div>
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
