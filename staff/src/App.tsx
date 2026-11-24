import { Navigate, Route, Routes } from 'react-router-dom'
import RequireAuth from './components/RequireAuth'
import AppShell from './components/AppShell'
import LoginPage from './pages/LoginPage'
import QueuePage from './pages/queue/QueuePage'
import DisplayPage from './pages/display/DisplayPage'
import UsersPage from './pages/admin/UsersPage'
import PatientsPage from './pages/admin/PatientsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/display" element={<DisplayPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/queue" element={<QueuePage />} />
        </Route>
      </Route>
      <Route element={<RequireAuth role="admin" />}>
        <Route element={<AppShell />}>
          <Route path="/admin/users" element={<UsersPage />} />
          <Route path="/admin/patients" element={<PatientsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/queue" replace />} />
    </Routes>
  )
}
