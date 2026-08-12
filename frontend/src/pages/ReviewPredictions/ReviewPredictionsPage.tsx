import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import LedgerTypeahead from '../../components/transactions/LedgerTypeahead'
import { ReviewFlagBadges } from '../../components/transactions/TransactionBadges'
import Pagination from '../../components/ui/Pagination'
import { formatAmount, formatDate } from '../../lib/format'
import { transactionService } from '../../services/transactionService'
import type { ParsedTransaction } from '../../types/transaction'

const PAGE_SIZE = 20

function ReviewRow({ transaction }: { transaction: ParsedTransaction }) {
  const queryClient = useQueryClient()
  const [pendingLedger, setPendingLedger] = useState<{ id: string; name: string } | null>(null)

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['transactions', transaction.processing_job_id] })
    queryClient.invalidateQueries({ queryKey: ['job', transaction.processing_job_id] })
  }

  const patchMutation = useMutation({
    mutationFn: (ledgerId: string) => transactionService.patchLedger(transaction.id, ledgerId),
    onSuccess: invalidate,
  })
  const approveMutation = useMutation({
    mutationFn: () => transactionService.approve(transaction.id),
    onSuccess: invalidate,
  })
  const duplicateMutation = useMutation({
    mutationFn: () => transactionService.markDuplicate(transaction.id, true),
    onSuccess: invalidate,
  })

  const isBusy = patchMutation.isPending || approveMutation.isPending || duplicateMutation.isPending
  const currentLedgerName = pendingLedger?.name ?? null

  return (
    <div className="flex flex-col gap-3 rounded border p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm text-gray-500">{formatDate(transaction.txn_date)}</p>
          <ReviewFlagBadges
            requiresReview={transaction.requires_review}
            isDuplicate={transaction.is_duplicate}
          />
        </div>
        <p className="mt-1 truncate font-medium" title={transaction.original_narration}>
          {transaction.normalized_narration ?? transaction.original_narration}
        </p>
        <p className="mt-1 text-sm text-gray-600">
          {transaction.debit !== '0' && transaction.debit !== '0.00'
            ? `Debit ₹${formatAmount(transaction.debit)}`
            : `Credit ₹${formatAmount(transaction.credit)}`}
          {transaction.confidence !== null && ` · AI confidence ${transaction.confidence}%`}
        </p>
        {transaction.validation_errors && transaction.validation_errors.length > 0 && (
          <ul className="mt-2 list-inside list-disc text-xs text-red-600">
            {transaction.validation_errors.map((error, index) => (
              <li key={index}>{error}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-col items-start gap-2 sm:items-end">
        <LedgerTypeahead
          currentLedgerName={currentLedgerName}
          similarCandidates={transaction.similar_candidates}
          disabled={isBusy}
          onSelect={(ledgerId, ledgerName) => {
            setPendingLedger({ id: ledgerId, name: ledgerName })
            patchMutation.mutate(ledgerId)
          }}
        />
        <div className="flex gap-2">
          <button
            type="button"
            disabled={isBusy || transaction.ledger_id === null}
            onClick={() => approveMutation.mutate()}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white disabled:opacity-40"
          >
            Approve
          </button>
          <button
            type="button"
            disabled={isBusy}
            onClick={() => duplicateMutation.mutate()}
            className="rounded border px-3 py-1 text-sm disabled:opacity-40"
          >
            Mark duplicate
          </button>
        </div>
        {(patchMutation.isError || approveMutation.isError || duplicateMutation.isError) && (
          <p className="text-xs text-red-600">Something went wrong. Please try again.</p>
        )}
      </div>
    </div>
  )
}

export default function ReviewPredictionsPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['transactions', jobId, page, 'true', 'all'],
    queryFn: () =>
      transactionService.listForJob(jobId as string, page, PAGE_SIZE, { requires_review: true }),
    enabled: Boolean(jobId),
  })

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Review Predictions</h1>
        <div className="flex gap-3 text-sm">
          <Link to={`/jobs/${jobId}`} className="underline">
            Processing status
          </Link>
          <Link to={`/jobs/${jobId}/transactions`} className="underline">
            All transactions
          </Link>
        </div>
      </div>
      <p className="mt-1 text-sm text-gray-500">
        Assign a ledger and approve, or mark as a duplicate to exclude it from export.
      </p>

      <div className="mt-6 flex flex-col gap-3">
        {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
        {!isLoading && data?.items.length === 0 && (
          <p className="rounded border border-dashed p-8 text-center text-sm text-gray-500">
            Nothing needs review right now.
          </p>
        )}
        {data?.items.map((txn) => (
          <ReviewRow key={txn.id} transaction={txn} />
        ))}
      </div>

      {data && data.total > 0 && (
        <div className="mt-4">
          <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
        </div>
      )}
    </div>
  )
}
