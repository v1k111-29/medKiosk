import axios from 'axios'
import { useAuth } from '../store/auth'

export const API_BASE: string = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export const http = axios.create({ baseURL: API_BASE })

http.interceptors.request.use((config) => {
  const token = useAuth.getState().token
  if (token) config.headers.set('Authorization', `Bearer ${token}`)
  return config
})

http.interceptors.response.use(
  (res) => res,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const isLogin = error.config?.url?.includes('/auth/login') ?? false
      if (!isLogin && useAuth.getState().token) {
        useAuth.getState().logout()
        if (window.location.pathname !== '/login') window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

/** Human-readable message from an API error. */
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data: unknown = error.response?.data
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
    }
    if (!error.response) return 'Cannot reach server'
    return `Request failed (${error.response.status})`
  }
  return error instanceof Error ? error.message : 'Unexpected error'
}

/** Build a ws:// or wss:// URL for a path, honouring VITE_API_URL. */
export function wsUrl(path: string, params?: Record<string, string>): string {
  const base = API_BASE || window.location.origin
  const url = new URL(path, base)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  if (params) for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v)
  return url.toString()
}
