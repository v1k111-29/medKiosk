import { http } from './client'
import type { CreateUserBody, FaceDeleteResponse, Patient, UpdateUserBody, User } from './types'

/** Contract does not fix the list shape; accept a bare array or {users: [...]}. */
export async function listUsers(): Promise<User[]> {
  const { data } = await http.get<User[] | { users: User[] }>('/admin/users')
  return Array.isArray(data) ? data : data.users
}

export async function createUser(body: CreateUserBody): Promise<User> {
  const { data } = await http.post<User>('/admin/users', body)
  return data
}

export async function updateUser(id: number, body: UpdateUserBody): Promise<User> {
  const { data } = await http.patch<User>(`/admin/users/${id}`, body)
  return data
}

export async function listPatients(): Promise<Patient[]> {
  const { data } = await http.get<Patient[]>('/patients')
  return data
}

export async function deleteFaceData(id: number): Promise<FaceDeleteResponse> {
  const { data } = await http.delete<FaceDeleteResponse>(`/patients/${id}/face`)
  return data
}
