import { create } from 'zustand';
import { fetchDepartments, Department, BookingResult, Urgency } from '../services/api';

export type KioskStep =
  | 'SPLASH'
  | 'LANGUAGE'
  | 'CONSENT'    // face-data consent (before any capture that could be stored)
  | 'PHONE'      // phone + OTP identification for visitors who decline face
  | 'SCAN'
  | 'REGISTER'
  | 'MENU'
  | 'CONVERSATION'
  | 'TRIAGE'
  | 'DEPARTMENT'
  | 'VITALS'
  | 'CONFIRM'
  | 'EMERGENCY'; // "go to ER now" screen when server urgency is emergency

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
  urgency: Urgency;
  /** Why the server raised urgency (red flags, NEWS2). Display only. */
  escalationReasons: string[];
  doctorId: number | null;
  doctorName: string;
}

export interface VitalsData {
  height: string;
  weight: string;
  bp_sys: string;
  bp_dia: string;
  spo2: string;
  pulse: string;
  temperature: string;
  resp_rate: string;
  glucose: string;
  diabetes: boolean;
  hypertension: boolean;
}

interface KioskState {
  step: KioskStep;
  language: 'en' | 'ta';
  patient: Patient | null;
  tempEmbedding: string | null;
  tempGender: string | null;
  /** null = not asked yet; true = agreed to face template storage; false = declined (phone ID). */
  faceConsent: boolean | null;
  /** 10-digit number verified by OTP (face opt-out path), prefilled on registration. */
  verifiedPhone: string | null;
  triage: TriageData;
  vitals: VitalsData;
  /** Server-issued booking (token, room, queue position...). Null until booked. */
  booking: BookingResult | null;
  smsOptIn: boolean;

  departments: Department[];
  departmentsStatus: 'idle' | 'loading' | 'ready' | 'error';
  loadDepartments: (force?: boolean) => Promise<void>;

  setStep: (s: KioskStep) => void;
  setLanguage: (l: 'en' | 'ta') => void;
  setPatient: (p: Patient | null) => void;
  setTempEmbedding: (e: string | null) => void;
  setTempGender: (g: string | null) => void;
  setFaceConsent: (c: boolean | null) => void;
  setVerifiedPhone: (p: string | null) => void;
  setTriage: (t: Partial<TriageData>) => void;
  setVitals: (v: Partial<VitalsData>) => void;
  setBooking: (b: BookingResult | null) => void;
  setSmsOptIn: (v: boolean) => void;
  reset: () => void;
}

const defaultTriage: TriageData = {
  service: null,
  symptoms: '',
  deptId: '',
  urgency: 'normal',
  escalationReasons: [],
  doctorId: null,
  doctorName: '',
};

const defaultVitals: VitalsData = {
  height: '', weight: '', bp_sys: '', bp_dia: '', spo2: '',
  pulse: '', temperature: '', resp_rate: '', glucose: '',
  diabetes: false, hypertension: false,
};

export const useKioskStore = create<KioskState>((set, get) => ({
  step: 'SPLASH',
  language: 'en',
  patient: null,
  tempEmbedding: null,
  tempGender: null,
  faceConsent: null,
  verifiedPhone: null,
  triage: defaultTriage,
  vitals: defaultVitals,
  booking: null,
  smsOptIn: false,

  departments: [],
  departmentsStatus: 'idle',
  loadDepartments: async (force = false) => {
    const { departmentsStatus } = get();
    if (departmentsStatus === 'loading') return;
    if (departmentsStatus === 'ready' && !force) return;
    set({ departmentsStatus: 'loading' });
    try {
      const departments = await fetchDepartments();
      set({ departments, departmentsStatus: 'ready' });
    } catch {
      set({ departmentsStatus: 'error' });
    }
  },

  setStep: (step) => set({ step }),
  setLanguage: (language) => set({ language }),
  setPatient: (patient) => set({ patient }),
  setTempEmbedding: (tempEmbedding) => set({ tempEmbedding }),
  setTempGender: (tempGender) => set({ tempGender }),
  setFaceConsent: (faceConsent) => set({ faceConsent }),
  setVerifiedPhone: (verifiedPhone) => set({ verifiedPhone }),
  setTriage: (t) => set((s) => ({ triage: { ...s.triage, ...t } })),
  setVitals: (v) => set((s) => ({ vitals: { ...s.vitals, ...v } })),
  setBooking: (booking) => set({ booking }),
  setSmsOptIn: (smsOptIn) => set({ smsOptIn }),
  reset: () => set({
    step: 'SPLASH',
    patient: null,
    tempEmbedding: null,
    tempGender: null,
    faceConsent: null,
    verifiedPhone: null,
    triage: defaultTriage,
    vitals: defaultVitals,
    booking: null,
    smsOptIn: false,
  }),
}));

/** Look up a department from the cached API list. */
export function findDepartment(departments: Department[], id: string): Department | undefined {
  return departments.find((d) => d.id === id);
}

export function deptLabel(d: Department | undefined, lang: 'en' | 'ta'): string {
  if (!d) return '';
  return lang === 'ta' ? d.name_ta : d.name_en;
}
