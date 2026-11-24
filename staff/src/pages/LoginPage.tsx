import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Loader2, Stethoscope } from 'lucide-react'
import { login } from '../api/auth'
import { errorMessage } from '../api/client'
import { useAuth } from '../store/auth'

export default function LoginPage() {
  const { token, user, setSession } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (token && user) return <Navigate to="/queue" replace />

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await login(username.trim(), password)
      setSession(res.access_token, res.user)
      navigate('/queue', { replace: true })
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-secondary px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-8 shadow-lg">
        <div className="flex items-center gap-2 text-xl font-bold text-primary">
          <Stethoscope className="h-7 w-7" /> medKiosk Staff
        </div>
        <label className="block text-sm font-medium text-dark">
          Username
          <input
            className="mt-1 w-full rounded-lg border px-3 py-2"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </label>
        <label className="block text-sm font-medium text-dark">
          Password
          <input
            type="password"
            className="mt-1 w-full rounded-lg border px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 font-semibold text-white disabled:opacity-60"
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} Sign in
        </button>
        {import.meta.env.DEV && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Demo accounts (dev only): nurse1 / Nurse@123, admin / Admin@123
          </p>
        )}
      </form>
    </div>
  )
}
