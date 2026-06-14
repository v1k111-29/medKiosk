export interface Dept {
  id: string;
  icon: string;
  en: string;
  ta: string;
  room: string;
  waitMins: number;
  color: string;
}

export const DEPARTMENTS: Dept[] = [
  { id: 'general',   icon: '🩺', en: 'General Medicine',  ta: 'பொது மருத்துவம்',    room: 'OPD-1', waitMins: 12, color: '#2E7D96' },
  { id: 'cardio',    icon: '❤️',  en: 'Cardiology',         ta: 'இதய நோயியல்',       room: 'OPD-3', waitMins: 25, color: '#C8393F' },
  { id: 'ortho',     icon: '🦴', en: 'Orthopaedics',       ta: 'எலும்பு சிகிச்சை',  room: 'OPD-4', waitMins: 20, color: '#7B5EA7' },
  { id: 'paeds',     icon: '👶', en: 'Paediatrics',        ta: 'குழந்தை நலம்',       room: 'OPD-2', waitMins: 10, color: '#1F7A5C' },
  { id: 'gyne',      icon: '🌸', en: 'Gynaecology',        ta: 'மகளிர் நலம்',        room: 'OPD-5', waitMins: 18, color: '#D04B8A' },
  { id: 'derm',      icon: '🧴', en: 'Dermatology',        ta: 'தோல் நோய்',          room: 'OPD-6', waitMins: 12, color: '#B45309' },
  { id: 'ent',       icon: '👂', en: 'ENT',                ta: 'காது மூக்கு தொண்டை', room: 'OPD-7', waitMins: 15, color: '#0369A1' },
  { id: 'ophthal',   icon: '👁️', en: 'Ophthalmology',      ta: 'கண் நோய்',           room: 'OPD-8', waitMins: 20, color: '#065F46' },
  { id: 'emergency', icon: '🚨', en: 'Emergency',          ta: 'அவசர சிகிச்சை',     room: 'ER-1',  waitMins:  0, color: '#C8393F' },
];
