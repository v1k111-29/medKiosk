import { http } from './client'
import type { QueueAction, QueueItem, QueueResponse } from './types'

export async function fetchQueue(deptId?: string): Promise<QueueResponse> {
  const { data } = await http.get<QueueResponse>('/queue', {
    params: deptId ? { dept_id: deptId } : undefined,
  })
  return data
}

export async function queueAction(id: number, action: QueueAction): Promise<QueueItem> {
  const { data } = await http.post<QueueItem>(`/queue/${id}/${action}`)
  return data
}

export async function callNext(deptId: string): Promise<QueueItem> {
  const { data } = await http.post<QueueItem>('/queue/call-next', null, {
    params: { dept_id: deptId },
  })
  return data
}
