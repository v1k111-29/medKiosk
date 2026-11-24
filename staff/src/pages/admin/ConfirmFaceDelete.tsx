import { Loader2 } from 'lucide-react'
import type { Patient } from '../../api/types'

interface Props {
  patient: Patient
  busy: boolean
  onCancel: () => void
  onConfirm: () => void
}

export default function ConfirmFaceDelete({ patient, busy, onCancel, onConfirm }: Props) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="w-full max-w-md space-y-4 rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-bold text-dark">Delete face data?</h2>
        <p className="text-sm text-gray-700">
          This permanently deletes all stored face templates for <b>{patient.name}</b> (ID {patient.id}) and
          turns face consent off. The patient record, visits and vitals are kept, and the patient can still
          check in by phone OTP. This cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <button onClick={onCancel} disabled={busy} className="rounded-lg border px-4 py-2 text-sm">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} Delete face data
          </button>
        </div>
      </div>
    </div>
  )
}
