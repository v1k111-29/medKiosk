import axios from 'axios';

/**
 * Unified API client for all backend requests.
 *
 * Uses relative base URL so it works on localhost, LAN, and production
 * without hardcoding. Set VITE_API_URL in .env for custom deployments.
 * Set VITE_KIOSK_KEY to the device key registered in the backend's
 * KIOSK_DEVICE_KEYS; it is sent as the X-Kiosk-Key header.
 */
const BASE_URL = import.meta.env.VITE_API_URL ?? '';
const KIOSK_KEY = import.meta.env.VITE_KIOSK_KEY;

export const faceApi = axios.create({
  baseURL: BASE_URL,
  timeout: 60000, // 60s — generous for Whisper + LLM
});

faceApi.interceptors.request.use((config) => {
  if (KIOSK_KEY) config.headers.set('X-Kiosk-Key', KIOSK_KEY);
  return config;
});

// Alias for backward compat
export const whisperApi = faceApi;

// ── Contract types (docs/CONTRACT.md) ───────────────────────────────────────

export type Urgency = 'normal' | 'urgent' | 'emergency';
export type SmsStatus = 'not_requested' | 'sent' | 'failed' | 'mocked';

export interface Department {
  id: string;
  name_en: string;
  name_ta: string;
  room: string;
  token_prefix: string;
  avg_wait_mins: number;
  color: string;
  icon: string;
  active: boolean;
}

export interface BookingResult {
  appointment_id: number;
  token: string;
  token_number: number;
  dept_id: string;
  dept_name: string;
  room: string;
  queue_position: number;
  wait_mins: number;
  service: string;
  symptoms: string | null;
  urgency: Urgency;
  escalation_reasons?: string[];
  doctor_id: number | null;
  doctor_name: string | null;
  sms_status: SmsStatus;
  created_at: string;
  status: string;
}

export interface BookingRequest {
  patient_id: number;
  dept_id: string;
  symptoms: string | null;
  service: string;
  urgency: Urgency;
  sms_opt_in: boolean;
  doctor_id: number | null;
  doctor_name: string | null;
}

export async function fetchDepartments(): Promise<Department[]> {
  const res = await faceApi.get<{ departments: Department[] }>('/departments');
  return res.data?.departments ?? [];
}

export async function bookAppointment(req: BookingRequest): Promise<BookingResult> {
  const res = await faceApi.post<BookingResult>('/appointment/book', req);
  return res.data;
}

/** Extract a human-readable message from an axios/unknown error. */
export function errorDetail(err: unknown, fallback: string, lang: 'en' | 'ta' = 'en'): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data as { detail?: unknown; message?: { en?: string; ta?: string } } | undefined;
    if (typeof d?.detail === 'string') return d.detail;
    const m = d?.message?.[lang] ?? d?.message?.en;
    if (typeof m === 'string') return m;
  }
  return fallback;
}

// ── Triage (server applies the deterministic safety layer) ───────────────────

export interface News2 {
  score: number;
  band: 'low' | 'low-medium' | 'medium' | 'high';
  points: Record<string, number>;
  any_single_3: boolean;
  partial: boolean;
  missing: string[];
}

export interface TriageResult {
  intent: string;
  service: string;
  dept_id: string | null;
  dept_name: string | null;
  dept_name_ta: string | null;
  room: string | null;
  wait_mins: number;
  symptoms: string | null;
  urgency: Urgency;
  confidence: number;
  reply: string;
  escalation_reasons: string[];
  red_flags: string[];
  news2: News2 | null;
}

export async function triageSymptoms(text: string, language: string, patientId?: number | null, age?: number | null): Promise<TriageResult> {
  const res = await faceApi.post<TriageResult>('/conversation/triage', {
    text, language, patient_id: patientId ?? null, age: age ?? null,
  });
  return res.data;
}

// ── Phone identification (face opt-out) ─────────────────────────────────────

export interface IdentifiedPatient {
  status: 'found';
  id: number;
  name: string;
  gender: string;
  age: number | null;
  phone: string | null;
  visits: number | null;
  other_patients?: IdentifiedPatient[];
}

export type PhoneVerifyResult = IdentifiedPatient | { status: 'new'; phone: string };

export async function phoneStart(phone: string): Promise<void> {
  await faceApi.post('/identify/phone/start', { phone });
}

export async function phoneVerify(phone: string, otp: string): Promise<PhoneVerifyResult> {
  const res = await faceApi.post<PhoneVerifyResult>('/identify/phone/verify', { phone, otp });
  return res.data;
}
