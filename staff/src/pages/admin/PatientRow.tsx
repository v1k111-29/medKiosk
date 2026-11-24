import { ScanFace } from 'lucide-react'
import clsx from 'clsx'
import type { Patient } from '../../api/types'

interface Props {
  patient: Patient
  onDeleteFace: (p: Patient) => void
}

export default function PatientRow({ patient: p, onDeleteFace }: Props) {
  const demo = [p.age != null ? `${p.age}y` : null, p.gender].filter(Boolean).join(' · ')
  return (
    <tr className="border-t">
      <td className="px-4 py-2 text-gray-500">{p.id}</td>
      <td className="px-4 py-2 font-medium text-dark">{p.name}</td>
      <td className="px-4 py-2">{demo || '--'}</td>
      <td className="px-4 py-2">{p.phone ?? '--'}</td>
      <td className="px-4 py-2">{p.visit_count}</td>
      <td className="px-4 py-2">
        <span
          className={clsx(
            'rounded-full px-2 py-0.5 text-xs font-semibold',
            p.face_consent ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600',
          )}
        >
          {p.face_consent ? 'Consented' : 'No consent / deleted'}
        </span>
      </td>
      <td className="px-4 py-2 text-right">
        <button
          onClick={() => onDeleteFace(p)}
          disabled={!p.face_consent}
          className="inline-flex items-center gap-1 rounded-lg border border-red-300 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ScanFace className="h-3.5 w-3.5" /> Delete face data
        </button>
      </td>
    </tr>
  )
}
