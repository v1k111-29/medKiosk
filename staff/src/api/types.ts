export type Role = 'nurse' | 'admin'
export type QueueStatus = 'waiting' | 'called' | 'in_consult' | 'done' | 'no_show'
export type Urgency = 'normal' | 'urgent' | 'emergency'

export interface User {
  id: number
  username: string
  full_name: string
  role: Role
  active?: boolean
  created_at?: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Department {
  id: string
  name_en: string
  name_ta: string
  room: string
  token_prefix: string
  avg_wait_mins: number
  color: string
  icon: string
  active: boolean
}

export interface QueuePatient {
  id: number
  name: string
  age: number | null
  gender: string | null
  phone_masked: string | null
}

export type News2Band = 'low' | 'low-medium' | 'medium' | 'high'

export interface News2 {
  score: number
  points: Record<string, number>
  band: News2Band
  any_single_3: boolean
  partial: boolean
  missing: string[]
}

export interface Patient {
  id: number
  name: string
  gender: string | null
  age: number | null
  phone: string | null
  blood_group: string | null
  visit_count: number
  created_at: string
  face_consent: boolean
}

export interface FaceDeleteResponse {
  status: 'face_deleted'
  id: number
  templates_deleted: number
  face_consent: boolean
}

export interface QueueVitals {
  bp_sys: number | null
  bp_dia: number | null
  spo2: number | null
  pulse: number | null
  temperature: number | null
  resp_rate: number | null
  glucose: number | null
  flags: string[]
  news2: News2 | null
}

export interface QueueItem {
  appointment_id: number
  token: string
  dept_id: string
  dept_name: string
  room: string
  status: QueueStatus
  urgency: Urgency
  escalation_reasons: string[]
  symptoms: string | null
  created_at: string
  called_at: string | null
  patient: QueuePatient
  vitals: QueueVitals | null
}

export type QueueCounts = Record<QueueStatus, number>

export interface QueueResponse {
  date: string
  items: QueueItem[]
  counts: QueueCounts
}

export type QueueAction = 'call' | 'start' | 'complete' | 'no-show' | 'requeue'

export interface CalledToken {
  token: string
  room: string
  dept_id: string
  dept_name: string
  called_at: string
}

export type WaitingCounts = Record<string, number>

export interface NowServingResponse {
  now_serving: CalledToken[]
  waiting_counts: WaitingCounts
}

export interface CreateUserBody {
  username: string
  password: string
  full_name: string
  role: Role
}

export interface UpdateUserBody {
  active?: boolean
  password?: string
  full_name?: string
  role?: Role
}

export interface QueueWsMessage {
  type: 'queue.updated'
  data: QueueItem
}

export type DisplayWsMessage =
  | { type: 'token.called'; data: CalledToken }
  | { type: 'counts'; data: WaitingCounts }
