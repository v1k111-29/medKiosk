import { create } from 'zustand';

export type KioskStep =
  | 'SPLASH'
  | 'LANGUAGE'
  | 'SCAN'
  | 'REGISTER'
  | 'MENU'
  | 'CONVERSATION'
  | 'TRIAGE'
  | 'DEPARTMENT'
  | 'VITALS'
  | 'CONFIRM';

export interface Patient {
  id: number;
  name: string;
  age?: number;
  gender?: string;
  phone?: string;
  visits?: number;
  blood_group?: string;
  city?: string;
}

export interface TriageData {
  service: 'symptoms' | 'appointment' | 'followup' | 'emergency' | null;
  symptoms: string;
  deptId: string;
  deptName: string;
  deptNameTa: string;
  room: string;
  waitMins: number;
}

export interface VitalsData {
  height: string;
  weight: string;
  bp_sys: string;
  bp_dia: string;
  spo2: string;
  diabetes: boolean;
  hypertension: boolean;
}

interface KioskState {
  step: KioskStep;
  language: 'en' | 'ta';
  patient: Patient | null;
  tempEmbedding: string | null;
  tempGender: string | null;
  triage: TriageData;
  vitals: VitalsData;
  token: string;

  setStep: (s: KioskStep) => void;
  setLanguage: (l: 'en' | 'ta') => void;
  setPatient: (p: Patient | null) => void;
  setTempEmbedding: (e: string | null) => void;
  setTempGender: (g: string | null) => void;
  setTriage: (t: Partial<TriageData>) => void;
  setVitals: (v: Partial<VitalsData>) => void;
  setToken: (t: string) => void;
  reset: () => void;
}

const defaultTriage: TriageData = {
  service: null,
  symptoms: '',
  deptId: '',
  deptName: '',
  deptNameTa: '',
  room: '',
  waitMins: 15,
};

const defaultVitals: VitalsData = {
  height: '', weight: '', bp_sys: '', bp_dia: '', spo2: '',
  diabetes: false, hypertension: false,
};

export const useKioskStore = create<KioskState>((set) => ({
  step: 'SPLASH',
  language: 'en',
  patient: null,
  tempEmbedding: null,
  tempGender: null,
  triage: defaultTriage,
  vitals: defaultVitals,
  token: '',

  setStep: (step) => set({ step }),
  setLanguage: (language) => set({ language }),
  setPatient: (patient) => set({ patient }),
  setTempEmbedding: (tempEmbedding) => set({ tempEmbedding }),
  setTempGender: (tempGender) => set({ tempGender }),
  setTriage: (t) => set((s) => ({ triage: { ...s.triage, ...t } })),
  setVitals: (v) => set((s) => ({ vitals: { ...s.vitals, ...v } })),
  setToken: (token) => set({ token }),
  reset: () => set({
    step: 'SPLASH',
    patient: null,
    tempEmbedding: null,
    tempGender: null,
    triage: defaultTriage,
    vitals: defaultVitals,
    token: '',
  }),
}));
