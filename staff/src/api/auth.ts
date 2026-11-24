import { http } from './client'
import type { LoginResponse, User } from './types'

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await http.post<LoginResponse>('/auth/login', { username, password })
  return data
}

export async function me(): Promise<User> {
  const { data } = await http.get<User>('/auth/me')
  return data
}
