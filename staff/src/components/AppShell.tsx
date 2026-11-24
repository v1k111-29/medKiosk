import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LogOut, Monitor, ScanFace, Stethoscope, Users } from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../store/auth'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  clsx(
    'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition',
    isActive ? 'bg-primary text-white' : 'text-dark hover:bg-secondary',
  )

export default function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const onLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-secondary">
      <header className="sticky top-0 z-10 border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <div className="flex items-center gap-2 text-lg font-bold text-primary">
            <Stethoscope className="h-6 w-6" /> medKiosk Staff
          </div>
          <nav className="flex flex-1 items-center gap-1">
            <NavLink to="/queue" className={linkClass}>
              <Stethoscope className="h-4 w-4" /> Queue
            </NavLink>
            {user?.role === 'admin' && (
              <NavLink to="/admin/users" className={linkClass}>
                <Users className="h-4 w-4" /> Users
              </NavLink>
            )}
            {user?.role === 'admin' && (
              <NavLink to="/admin/patients" className={linkClass}>
                <ScanFace className="h-4 w-4" /> Patients
              </NavLink>
            )}
            <a
              href="/display"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-dark hover:bg-secondary"
            >
              <Monitor className="h-4 w-4" /> Display board
            </a>
          </nav>
          <div className="text-right text-sm leading-tight">
            <div className="font-semibold text-dark">{user?.full_name}</div>
            <div className="text-xs uppercase tracking-wide text-gray-500">{user?.role}</div>
          </div>
          <button
            onClick={onLogout}
            className="flex items-center gap-1 rounded-lg border px-3 py-2 text-sm text-dark hover:bg-secondary"
          >
            <LogOut className="h-4 w-4" /> Logout
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
