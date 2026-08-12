import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { jobService } from '../../services/jobService'
import { TERMINAL_JOB_STATUSES } from '../../types/job'

export default function ProcessingStatusPage() {
  const { jobId } = useParams<{ jobId: string }>()

  const { data: job, isLoading, isError } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobService.get(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && TERMINAL_JOB_STATUSES.includes(status) ? false : 2000
    },
  })

  if (isLoading) {
    return <div className="mx-auto max-w-2xl px-4 py-8 text-sm text-gray-500">Loading…</div>
  }

  if (isError || !job) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 text-sm text-red-600">
        Could not load this job. It may not exist or you may not have access to it.
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Processing Status</h1>
        <Link to="/dashboard" className="text-sm underline">
          Back to dashboard
        </Link>
      </div>

      <p className="mt-2 text-sm text-gray-500">Job ID: {job.id}</p>

      <div className="mt-6 rounded border p-4">
        <p className="text-sm font-medium">
          Current status: <span className="font-semibold">{job.status}</span>
        </p>
        {job.error_message && (
          <p className="mt-2 text-sm text-red-600">{job.error_message}</p>
        )}
      </div>

      <ol className="mt-6 flex flex-col gap-2">
        {job.status_history.map((entry, index) => (
          <li key={index} className="flex items-center justify-between rounded border px-3 py-2 text-sm">
            <span>{entry.status}</span>
            <span className="text-gray-500">{new Date(entry.timestamp).toLocaleString()}</span>
          </li>
        ))}
      </ol>

      <dl className="mt-6 grid grid-cols-2 gap-4 text-sm">
        <div className="rounded border p-3">
          <dt className="text-gray-500">Total transactions</dt>
          <dd className="text-lg font-semibold">{job.total_transactions}</dd>
        </div>
        <div className="rounded border p-3">
          <dt className="text-gray-500">Auto matched</dt>
          <dd className="text-lg font-semibold">{job.auto_matched_count}</dd>
        </div>
        <div className="rounded border p-3">
          <dt className="text-gray-500">AI predicted</dt>
          <dd className="text-lg font-semibold">{job.ai_predicted_count}</dd>
        </div>
        <div className="rounded border p-3">
          <dt className="text-gray-500">Manual review required</dt>
          <dd className="text-lg font-semibold">{job.manual_review_count}</dd>
        </div>
      </dl>

      <div className="mt-6 flex gap-3">
        <Link to={`/jobs/${job.id}/transactions`} className="rounded border px-3 py-2 text-sm">
          View transactions
        </Link>
        {job.manual_review_count > 0 && (
          <Link to={`/jobs/${job.id}/review`} className="rounded bg-slate-900 px-3 py-2 text-sm text-white">
            Review {job.manual_review_count} transaction{job.manual_review_count === 1 ? '' : 's'}
          </Link>
        )}
        {(job.status === 'READY' || job.status === 'REVIEW_REQUIRED' || job.status === 'EXPORTED') && (
          <Link to={`/jobs/${job.id}/export`} className="rounded border px-3 py-2 text-sm">
            Export
          </Link>
        )}
      </div>
    </div>
  )
}
