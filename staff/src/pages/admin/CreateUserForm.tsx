import { useState } from 'react'
import type { FormEvent } from 'react'
import { UserPlus } from 'lucide-react'
import { createUser } from '../../api/admin'
import { errorMessage } from '../../api/client'
import type { Role, User } from '../../api/types'

export default function CreateUserForm({ onCreated }: { onCreated: (u: User) => void }) {
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<Role>('nurse')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const u = await createUser({ username: username.trim(), full_name: fullName.trim(), role, password })
      onCreated(u)
      setUsername('')
      setFullName('')
      setPassword('')
      setRole('nurse')
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const input = 'w-full rounded-lg border px-3 py-2 text-sm'
  return (
    <form onSubmit={onSubmit} className="space-y-3 rounded-xl bg-white p-4 shadow-sm">
      <h2 className="flex items-center gap-2 font-bold text-dark">
        <UserPlus className="h-5 w-5" /> New user
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <input className={input} placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        <input className={input} placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        <select className={input} value={role} onChange={(e) => setRole(e.target.value as Role)}>
          <option value="nurse">Nurse</option>
          <option value="admin">Admin</option>
        </select>
        <input className={input} type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required />
        <button type="submit" disabled={busy} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
          Create
        </button>
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
    </form>
  )
}
