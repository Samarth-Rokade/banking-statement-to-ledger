import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { exportService, type ExportFormat } from '../../services/exportService'
import { jobService } from '../../services/jobService'

const NOT_EXPORTABLE_STATUSES = new Set([
  'QUEUED',
  'PARSING',
  'NORMALIZING',
  'MATCHING',
  'AI_PREDICTING',
  'VALIDATING',
  'FAILED',
])

const FORMAT_LABELS: Record<ExportFormat, string> = {
  csv: 'CSV',
  excel: 'Excel',
  xml: 'Tally XML',
}

async function readErrorMessage(error: unknown): Promise<string> {
  const axiosError = error as { response?: { data?: Blob } }
  const blob = axiosError.response?.data
  if (!blob) return 'Export failed. Please try again.'
  try {
    const text = await blob.text()
    const parsed = JSON.parse(text) as { detail?: string }
    return parsed.detail ?? 'Export failed. Please try again.'
  } catch {
    return 'Export failed. Please try again.'
  }
}

export default function ExportPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const [force, setForce] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [pendingFormat, setPendingFormat] = useState<ExportFormat | null>(null)

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobService.get(jobId as string),
    enabled: Boolean(jobId),
  })

  const downloadMutation = useMutation({
    mutationFn: ({ format, force }: { format: ExportFormat; force: boolean }) =>
      exportService.download(jobId as string, format, force),
    onMutate: ({ format }) => {
      setErrorMessage(null)
      setPendingFormat(format)
    },
    onError: async (error) => setErrorMessage(await readErrorMessage(error)),
    onSettled: () => setPendingFormat(null),
  })

  if (isLoading) {
    return <div className="mx-auto max-w-2xl px-4 py-8 text-sm text-gray-500">Loading…</div>
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 text-sm text-red-600">
        Could not load this job.
      </div>
    )
  }

  const notExportable = NOT_EXPORTABLE_STATUSES.has(job.status)
  const needsReview = job.manual_review_count > 0
  const canExport = !notExportable && (!needsReview || force)

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Export</h1>
        <div className="flex gap-3 text-sm">
          <Link to={`/jobs/${jobId}`} className="underline">
            Processing status
          </Link>
          <Link to={`/jobs/${jobId}/transactions`} className="underline">
            All transactions
          </Link>
        </div>
      </div>

      <div className="mt-6 rounded border p-4">
        <h2 className="text-sm font-medium text-gray-500">Pre-export summary</h2>
        <dl className="mt-2 grid grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Total</dt>
            <dd className="text-lg font-semibold">{job.total_transactions}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Ready to export</dt>
            <dd className="text-lg font-semibold text-green-700">{job.export_ready_count}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Needs review</dt>
            <dd className="text-lg font-semibold text-amber-700">{job.manual_review_count}</dd>
          </div>
        </dl>
      </div>

      {notExportable && (
        <p className="mt-4 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          This job is still {job.status.toLowerCase()}. Come back once it finishes processing.
        </p>
      )}

      {!notExportable && needsReview && (
        <div className="mt-4 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          <p>
            {job.manual_review_count} transaction{job.manual_review_count === 1 ? '' : 's'} still
            need review.{' '}
            <Link to={`/jobs/${jobId}/review`} className="underline">
              Review them
            </Link>{' '}
            first, or export the {job.export_ready_count} ready row{job.export_ready_count === 1 ? '' : 's'}{' '}
            now and skip the rest.
          </p>
          <label className="mt-2 flex items-center gap-2">
            <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
            Export the ready rows now, skipping what still needs review
          </label>
        </div>
      )}

      <div className="mt-6 flex gap-3">
        {(Object.keys(FORMAT_LABELS) as ExportFormat[]).map((format) => (
          <button
            key={format}
            type="button"
            disabled={!canExport || downloadMutation.isPending}
            onClick={() => downloadMutation.mutate({ format, force })}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-40"
          >
            {pendingFormat === format ? 'Preparing…' : `Download ${FORMAT_LABELS[format]}`}
          </button>
        ))}
      </div>

      {errorMessage && <p className="mt-3 text-sm text-red-600">{errorMessage}</p>}
      {job.status === 'EXPORTED' && (
        <p className="mt-3 text-sm text-gray-500">
          This job was already exported at least once - re-downloading won't change that.
        </p>
      )}
    </div>
  )
}
