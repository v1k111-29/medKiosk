export interface DepartmentData {
  id: string;
  en: string;
  ta: string;
  room: string;
  waitMins: number;
  color: string;
  icon: string;
}

export const SYMPTOM_DEPT: Record<string, DepartmentData> = {
  general:      { id:'general',   en:'General Medicine', ta:'பொது மருத்துவம்',    room:'OPD-1', waitMins:12, color: '#2E7D96', icon: '🏥' },
  fever:        { id:'general',   en:'General Medicine', ta:'பொது மருத்துவம்',    room:'OPD-1', waitMins:12, color: '#2E7D96', icon: '🏥' },
  headache:     { id:'general',   en:'General Medicine', ta:'பொது மருத்துவம்',    room:'OPD-1', waitMins:12, color: '#2E7D96', icon: '🏥' },
  cough:        { id:'general',   en:'General Medicine', ta:'பொது மருத்துவம்',    room:'OPD-1', waitMins:12, color: '#2E7D96', icon: '🏥' },
  cardio:       { id:'cardio',    en:'Cardiology',       ta:'இதய நோயியல்',       room:'OPD-3', waitMins:25, color: '#DC2626', icon: '❤️' },
  chest:        { id:'cardio',    en:'Cardiology',       ta:'இதய நோயியல்',       room:'OPD-3', waitMins:25, color: '#DC2626', icon: '❤️' },
  heart:        { id:'cardio',    en:'Cardiology',       ta:'இதய நோயியல்',       room:'OPD-3', waitMins:25, color: '#DC2626', icon: '❤️' },
  ortho:        { id:'ortho',     en:'Orthopaedics',     ta:'எலும்பு சிகிச்சை',  room:'OPD-4', waitMins:20, color: '#7C3AED', icon: '🦴' },
  bone:         { id:'ortho',     en:'Orthopaedics',     ta:'எலும்பு சிகிச்சை',  room:'OPD-4', waitMins:20, color: '#7C3AED', icon: '🦴' },
  joint:        { id:'ortho',     en:'Orthopaedics',     ta:'எலும்பு சிகிச்சை',  room:'OPD-4', waitMins:20, color: '#7C3AED', icon: '🦴' },
  fracture:     { id:'ortho',     en:'Orthopaedics',     ta:'எலும்பு சிகிச்சை',  room:'OPD-4', waitMins:20, color: '#7C3AED', icon: '🦴' },
  paeds:        { id:'paeds',     en:'Paediatrics',      ta:'குழந்தை நலம்',       room:'OPD-2', waitMins:10, color: '#059669', icon: '👶' },
  child:        { id:'paeds',     en:'Paediatrics',      ta:'குழந்தை நலம்',       room:'OPD-2', waitMins:10, color: '#059669', icon: '👶' },
  baby:         { id:'paeds',     en:'Paediatrics',      ta:'குழந்தை நலம்',       room:'OPD-2', waitMins:10, color: '#059669', icon: '👶' },
  gyne:         { id:'gyne',      en:'Gynaecology',      ta:'மகளிர் நலம்',        room:'OPD-5', waitMins:18, color: '#DB2777', icon: '👩' },
  pregnancy:    { id:'gyne',      en:'Gynaecology',      ta:'மகளிர் நலம்',        room:'OPD-5', waitMins:18, color: '#DB2777', icon: '👩' },
  derm:         { id:'derm',      en:'Dermatology',      ta:'தோல் நோய்',          room:'OPD-6', waitMins:12, color: '#D97706', icon: '✨' },
  skin:         { id:'derm',      en:'Dermatology',      ta:'தோல் நோய்',          room:'OPD-6', waitMins:12, color: '#D97706', icon: '✨' },
  rash:         { id:'derm',      en:'Dermatology',      ta:'தோல் நோய்',          room:'OPD-6', waitMins:12, color: '#D97706', icon: '✨' },
  ent:          { id:'ent',       en:'ENT',               ta:'ENT',               room:'OPD-7', waitMins:15, color: '#4F46E5', icon: '👂' },
  ear:          { id:'ent',       en:'ENT',               ta:'ENT',               room:'OPD-7', waitMins:15, color: '#4F46E5', icon: '👂' },
  throat:       { id:'ent',       en:'ENT',               ta:'ENT',               room:'OPD-7', waitMins:15, color: '#4F46E5', icon: '👂' },
  ophthal:      { id:'ophthal',   en:'Ophthalmology',    ta:'கண் நோய்',           room:'OPD-8', waitMins:20, color: '#2563EB', icon: '👁️' },
  eye:          { id:'ophthal',   en:'Ophthalmology',    ta:'கண் நோய்',           room:'OPD-8', waitMins:20, color: '#2563EB', icon: '👁️' },
  vision:       { id:'ophthal',   en:'Ophthalmology',    ta:'கண் நோய்',           room:'OPD-8', waitMins:20, color: '#2563EB', icon: '👁️' },
};

export const DEPARTMENTS: DepartmentData[] = [
  { id: 'general',   en: 'General Medicine', ta: 'பொது மருத்துவம்',    room: 'OPD-1', waitMins: 12, color: '#2E7D96', icon: '🏥' },
  { id: 'cardio',    en: 'Cardiology',       ta: 'இதய நோயியல்',       room: 'OPD-3', waitMins: 25, color: '#DC2626', icon: '❤️' },
  { id: 'ortho',     en: 'Orthopaedics',     ta: 'எலும்பு சிகிச்சை',  room: 'OPD-4', waitMins: 20, color: '#7C3AED', icon: '🦴' },
  { id: 'paeds',     en: 'Paediatrics',      ta: 'குழந்தை நலம்',       room: 'OPD-2', waitMins: 10, color: '#059669', icon: '👶' },
  { id: 'gyne',      en: 'Gynaecology',      ta: 'மகளிர் நலம்',        room: 'OPD-5', waitMins: 18, color: '#DB2777', icon: '👩' },
  { id: 'derm',      en: 'Dermatology',      ta: 'தோல் நோய்',          room: 'OPD-6', waitMins: 12, color: '#D97706', icon: '✨' },
  { id: 'ent',       en: 'ENT',               ta: 'ENT',               room: 'OPD-7', waitMins: 15, color: '#4F46E5', icon: '👂' },
  { id: 'ophthal',   en: 'Ophthalmology',    ta: 'கண் நோய்',           room: 'OPD-8', waitMins: 20, color: '#2563EB', icon: '👁️' },
  { id: 'emergency', en: 'Emergency',       ta: 'அவசர சிகிச்சை',    room: 'ER-1',  waitMins: 0,  color: '#B91C1C', icon: '🚨' },
];

export function detectDept(text: string): DepartmentData {
  const lower = text.toLowerCase();
  for (const [kw, dept] of Object.entries(SYMPTOM_DEPT)) {
    if (lower.includes(kw)) return dept;
  }
  return SYMPTOM_DEPT['general'];
}
