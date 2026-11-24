import { useState } from 'react'
import clsx from 'clsx'
import { KeyRound } from 'lucide-react'
import type { User } from '../../api/types'

interface Props {
  user: User
  isSelf: boolean
  busy: boolean
  onToggleActive: (u: User) => void
  onResetPassword: (u: User, password: string) => Promise<boolean>
}

export default function UserRow({ user, isSelf, busy, onToggleActive, onResetPassword }: Props) {
  const [resetting, setResetting] = useState(false)
  const [pw, setPw] = useState('')
  const active = user.active !== false

  const submit = async () => {
    if (!pw) return
    if (await onResetPassword(user, pw)) {
      setResetting(false)
      setPw('')
    }
  }

  return (
    <tr className="border-t">
      <td className="px-4 py-3 font-medium text-dark">{user.username}</td>
      <td className="px-4 py-3">{user.full_name}</td>
      <td className="px-4 py-3 capitalize">{user.role}</td>
      <td className="px-4 py-3">
        <span className={clsx('rounded-full px-2.5 py-0.5 text-xs font-semibold', active ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-200 text-gray-600')}>
          {active ? 'Active' : 'Inactive'}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap items-center justify-end gap-2">
          {resetting ? (
            <>
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                placeholder="New password"
                autoComplete="new-password"
                className="rounded-lg border px-2 py-1 text-sm"
              />
              <button disabled={busy || !pw} onClick={submit} className="rounded-lg bg-primary px-3 py-1 text-sm font-semibold text-white disabled:opacity-50">
                Save
              </button>
              <button onClick={() => setResetting(false)} className="rounded-lg px-3 py-1 text-sm text-gray-600">
                Cancel
              </button>
            </>
          ) : (
            <>
              <button onClick={() => setResetting(true)} className="flex items-center gap-1 rounded-lg border px-3 py-1 text-sm">
                <KeyRound className="h-3.5 w-3.5" /> Reset password
              </button>
              <button
                disabled={busy || isSelf}
                title={isSelf ? 'You cannot deactivate yourself' : undefined}
                onClick={() => onToggleActive(user)}
                className="rounded-lg border px-3 py-1 text-sm disabled:opacity-40"
              >
                {active ? 'Deactivate' : 'Activate'}
              </button>
            </>
          )}
        </div>
      </td>
    </tr>
  )
}
