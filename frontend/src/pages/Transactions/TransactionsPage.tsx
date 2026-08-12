import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import TransactionsTable from '../../components/transactions/TransactionsTable'
import Pagination from '../../components/ui/Pagination'
import { useGroupLookup, useLedgerLookup } from '../../hooks/useLookups'
import { transactionService } from '../../services/transactionService'
import type { ResolutionSource } from '../../types/transaction'

const PAGE_SIZE = 50

const RESOLUTION_SOURCES: ResolutionSource[] = [
  'RULE',
  'EXACT_MATCH',
  'ALIAS_MATCH',
  'SIMILARITY_MATCH',
  'AI_PREDICTION',
  'MANUAL',
  'AI_FAILED',
]

export default function TransactionsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const [page, setPage] = useState(1)
  const [requiresReview, setRequiresReview] = useState<'all' | 'true' | 'false'>('all')
  const [resolutionSource, setResolutionSource] = useState<'all' | ResolutionSource>('all')

  const { ledgerNameById } = useLedgerLookup()
  const { groupNameById } = useGroupLookup()

  const { data, isLoading } = useQuery({
    queryKey: ['transactions', jobId, page, requiresReview, resolutionSource],
    queryFn: () =>
      transactionService.listForJob(jobId as string, page, PAGE_SIZE, {
        requires_review: requiresReview === 'all' ? undefined : requiresReview === 'true',
        resolution_source: resolutionSource === 'all' ? undefined : resolutionSource,
      }),
    enabled: Boolean(jobId),
  })

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Transactions</h1>
        <div className="flex gap-3 text-sm">
          <Link to={`/jobs/${jobId}`} className="underline">
            Processing status
          </Link>
          <Link to={`/jobs/${jobId}/review`} className="underline">
            Review predictions
          </Link>
          <Link to={`/jobs/${jobId}/export`} className="underline">
            Export
          </Link>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <select
          value={requiresReview}
          onChange={(event) => {
            setRequiresReview(event.target.value as typeof requiresReview)
            setPage(1)
          }}
          className="rounded border px-2 py-1 text-sm"
        >
          <option value="all">All transactions</option>
          <option value="true">Needs review</option>
          <option value="false">Resolved</option>
        </select>
        <select
          value={resolutionSource}
          onChange={(event) => {
            setResolutionSource(event.target.value as typeof resolutionSource)
            setPage(1)
          }}
          className="rounded border px-2 py-1 text-sm"
        >
          <option value="all">All sources</option>
          {RESOLUTION_SOURCES.map((source) => (
            <option key={source} value={source}>
              {source}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : (
          <TransactionsTable
            transactions={data?.items ?? []}
            ledgerNameById={ledgerNameById}
            groupNameById={groupNameById}
          />
        )}
      </div>

      {data && (
        <div className="mt-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
        </div>
      )}
    </div>
  )
}
