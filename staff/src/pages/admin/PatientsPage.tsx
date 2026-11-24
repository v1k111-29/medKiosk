import { useCallback, useEffect, useMemo, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import { deleteFaceData, listPatients } from '../../api/admin'
import { errorMessage } from '../../api/client'
import type { Patient } from '../../api/types'
import ConfirmFaceDelete from './ConfirmFaceDelete'
import PatientRow from './PatientRow'

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [target, setTarget] = useState<Patient | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setPatients(await listPatients())
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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return patients
    return patients.filter(
      (p) => p.name.toLowerCase().includes(q) || (p.phone ?? '').includes(q) || String(p.id) === q,
    )
  }, [patients, query])

  const confirmDelete = async () => {
    if (!target) return
    setBusy(true)
    try {
      const res = await deleteFaceData(target.id)
      setPatients((prev) => prev.map((p) => (p.id === res.id ? { ...p, face_consent: res.face_consent } : p)))
      setError(null)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
      setTarget(null)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-dark">Patients</h1>
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search name, phone or ID"
          className="w-full rounded-lg border py-2 pl-9 pr-3 text-sm"
        />
      </div>
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
                <th className="px-4 py-2">ID</th>
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Age / Sex</th>
                <th className="px-4 py-2">Phone</th>
                <th className="px-4 py-2">Visits</th>
                <th className="px-4 py-2">Face consent</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <PatientRow key={p.id} patient={p} onDeleteFace={setTarget} />
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-gray-400">
                    No patients found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {target && (
        <ConfirmFaceDelete
          patient={target}
          busy={busy}
          onCancel={() => setTarget(null)}
          onConfirm={() => void confirmDelete()}
        />
      )}
    </div>
  )
}
