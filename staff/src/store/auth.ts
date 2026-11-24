import { create } from 'zustand'
import type { User } from '../api/types'

const TOKEN_KEY = 'staff.token'
const USER_KEY = 'staff.user'

function readUser(): User | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

interface AuthState {
  token: string | null
  user: User | null
  setSession: (token: string, user: User) => void
  logout: () => void
}

export const useAuth = create<AuthState>((set) => ({
  token: readToken(),
  user: readUser(),
  setSession: (token, user) => {
    try {
      sessionStorage.setItem(TOKEN_KEY, token)
      sessionStorage.setItem(USER_KEY, JSON.stringify(user))
    } catch {
      /* storage unavailable: session lives in memory only */
    }
    set({ token, user })
  },
  logout: () => {
    try {
      sessionStorage.removeItem(TOKEN_KEY)
      sessionStorage.removeItem(USER_KEY)
    } catch {
      /* ignore */
    }
    set({ token: null, user: null })
  },
}))
