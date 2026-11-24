import { http } from './client'
import type { Department } from './types'

export async function listDepartments(): Promise<Department[]> {
  const { data } = await http.get<{ departments: Department[] }>('/departments')
  return data.departments
}
