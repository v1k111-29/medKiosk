import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../store/auth'
import type { Role } from '../api/types'

export default function RequireAuth({ role }: { role?: Role }) {
  const { token, user } = useAuth()
  const location = useLocation()
  if (!token || !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (role && user.role !== role) return <Navigate to="/queue" replace />
  return <Outlet />
}
