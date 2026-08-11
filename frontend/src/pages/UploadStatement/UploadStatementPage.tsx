import { useMutation } from '@tanstack/react-query'
import { type ChangeEvent, type DragEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobService } from '../../services/jobService'

const ACCEPTED_EXTENSIONS = ['.pdf', '.csv', '.xlsx', '.xls']

function hasAcceptedExtension(filename: string): boolean {
  const lower = filename.toLowerCase()
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext))
}

export default function UploadStatementPage() {
  const navigate = useNavigate()
  const [isDragging, setIsDragging] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  const uploadMutation = useMutation({
    mutationFn: (file: File) => jobService.upload(file),
    onSuccess: (data) => navigate(`/jobs/${data.job_id}`),
  })

  const handleFile = (file: File | undefined) => {
    setValidationError(null)
    if (!file) return
    if (!hasAcceptedExtension(file.name)) {
      setValidationError('Only PDF, CSV, and Excel (.xlsx/.xls) files are supported.')
      return
    }
    uploadMutation.mutate(file)
  }

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    handleFile(event.target.files?.[0])
  }

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    handleFile(event.dataTransfer.files?.[0])
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-2xl font-semibold">Upload Statement</h1>
      <p className="mt-1 text-sm text-gray-500">
        Upload a bank statement in PDF, CSV, or Excel format to start processing.
      </p>

      <div
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        className={`mt-6 flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-16 text-center transition-colors ${
          isDragging ? 'border-slate-900 bg-slate-50' : 'border-gray-300'
        }`}
      >
        <p className="text-sm text-gray-600">Drag and drop a file here, or</p>
        <label className="cursor-pointer rounded bg-slate-900 px-4 py-2 text-sm text-white">
          Browse files
          <input
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(',')}
            className="hidden"
            onChange={onInputChange}
            disabled={uploadMutation.isPending}
          />
        </label>
        {uploadMutation.isPending && <p className="text-sm text-gray-500">Uploading…</p>}
      </div>

      {validationError && <p className="mt-3 text-sm text-red-600">{validationError}</p>}
      {uploadMutation.isError && (
        <p className="mt-3 text-sm text-red-600">
          Upload failed. Please check the file and try again.
        </p>
      )}
    </div>
  )
}
