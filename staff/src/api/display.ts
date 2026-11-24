import { http } from './client'
import type { NowServingResponse } from './types'

export async function fetchNowServing(deptId?: string): Promise<NowServingResponse> {
  const { data } = await http.get<NowServingResponse>('/display/now-serving', {
    params: deptId ? { dept_id: deptId } : undefined,
  })
  return data
}
