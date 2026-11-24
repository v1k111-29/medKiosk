import { useCallback, useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { listUsers, updateUser } from '../../api/admin'
import { errorMessage } from '../../api/client'
import type { User } from '../../api/types'
import { useAuth } from '../../store/auth'
import CreateUserForm from './CreateUserForm'
import UserRow from './UserRow'

export default function UsersPage() {
  const me = useAuth((s) => s.user)
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const load = useCallback(async () => {
    try {
      setUsers(await listUsers())
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const replace = (u: User) => setUsers((prev) => prev.map((p) => (p.id === u.id ? { ...p, ...u } : p)))

  const onToggleActive = async (u: User) => {
    setBusyId(u.id)
    try {
      replace(await updateUser(u.id, { active: u.active === false }))
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  const onResetPassword = async (u: User, password: string): Promise<boolean> => {
    setBusyId(u.id)
    try {
      await updateUser(u.id, { password })
      setError(null)
      return true
    } catch (err) {
      setError(errorMessage(err))
      return false
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-dark">Staff users</h1>
      <CreateUserForm onCreated={(u) => setUsers((prev) => [...prev, u])} />
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {loading ? (
        <div className="flex justify-center py-12 text-gray-400">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-2">Username</th>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Role</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <UserRow
                  key={u.id}
                  user={u}
                  isSelf={u.id === me?.id}
                  busy={busyId === u.id}
                  onToggleActive={onToggleActive}
                  onResetPassword={onResetPassword}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
