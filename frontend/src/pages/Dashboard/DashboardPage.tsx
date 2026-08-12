import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { jobService } from '../../services/jobService'
import { useAuthStore } from '../../store/authStore'

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)

  const { data: jobsResponse, isLoading } = useQuery({
    queryKey: ['jobs', 1],
    queryFn: () => jobService.list(1, 20),
  })

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <button onClick={logout} className="rounded border px-3 py-1 text-sm">
          Log out
        </button>
      </div>
      <p className="mt-4 text-sm text-gray-500">
        Signed in as {user?.full_name ?? user?.email}.
      </p>

      <div className="mt-6 flex gap-3">
        <Link to="/upload" className="inline-block rounded bg-slate-900 px-4 py-2 text-sm text-white">
          Upload Statement
        </Link>
        <Link to="/ledgers" className="inline-block rounded border px-4 py-2 text-sm">
          Ledger Master
        </Link>
      </div>

      <h2 className="mt-8 text-lg font-semibold">Recent statements</h2>
      {isLoading && <p className="mt-2 text-sm text-gray-500">Loading…</p>}
      {!isLoading && jobsResponse?.items.length === 0 && (
        <p className="mt-2 text-sm text-gray-500">No statements uploaded yet.</p>
      )}
      <ul className="mt-2 flex flex-col gap-2">
        {jobsResponse?.items.map((job) => (
          <li key={job.id}>
            <Link
              to={`/jobs/${job.id}`}
              className="flex items-center justify-between rounded border px-3 py-2 text-sm hover:bg-gray-50"
            >
              <span>{new Date(job.created_at).toLocaleString()}</span>
              <span className="font-medium">{job.status}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
