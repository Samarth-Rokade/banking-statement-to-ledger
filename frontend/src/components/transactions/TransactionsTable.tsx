import type { ReactNode } from 'react'
import { formatAmount, formatDate } from '../../lib/format'
import type { ParsedTransaction } from '../../types/transaction'
import { ConfidenceBadge, ResolutionSourceBadge, ReviewFlagBadges } from './TransactionBadges'

export default function TransactionsTable({
  transactions,
  ledgerNameById,
  groupNameById,
  renderActions,
}: {
  transactions: ParsedTransaction[]
  ledgerNameById: Map<string, string>
  groupNameById: Map<string, string>
  renderActions?: (transaction: ParsedTransaction) => ReactNode
}) {
  return (
    <div className="overflow-x-auto rounded border">
      <table className="min-w-full divide-y text-sm">
        <thead className="bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
          <tr>
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">Narration</th>
            <th className="px-3 py-2 text-right">Debit</th>
            <th className="px-3 py-2 text-right">Credit</th>
            <th className="px-3 py-2">Ledger</th>
            <th className="px-3 py-2">Group</th>
            <th className="px-3 py-2">Confidence</th>
            <th className="px-3 py-2">Source</th>
            <th className="px-3 py-2">Flags</th>
            {renderActions && <th className="px-3 py-2">Actions</th>}
          </tr>
        </thead>
        <tbody className="divide-y">
          {transactions.map((txn) => (
            <tr key={txn.id} className={txn.is_duplicate ? 'bg-red-50/40' : undefined}>
              <td className="whitespace-nowrap px-3 py-2 text-gray-500">{formatDate(txn.txn_date)}</td>
              <td className="max-w-xs px-3 py-2">
                <p className="truncate" title={txn.original_narration}>
                  {txn.normalized_narration ?? txn.original_narration}
                </p>
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">
                {formatAmount(txn.debit)}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">
                {formatAmount(txn.credit)}
              </td>
              <td className="whitespace-nowrap px-3 py-2">
                {txn.ledger_id ? (ledgerNameById.get(txn.ledger_id) ?? '—') : '—'}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-gray-500">
                {txn.group_id ? (groupNameById.get(txn.group_id) ?? '—') : '—'}
              </td>
              <td className="whitespace-nowrap px-3 py-2">
                <ConfidenceBadge confidence={txn.confidence} />
              </td>
              <td className="whitespace-nowrap px-3 py-2">
                <ResolutionSourceBadge source={txn.resolution_source} />
              </td>
              <td className="whitespace-nowrap px-3 py-2">
                <ReviewFlagBadges requiresReview={txn.requires_review} isDuplicate={txn.is_duplicate} />
              </td>
              {renderActions && <td className="px-3 py-2">{renderActions(txn)}</td>}
            </tr>
          ))}
          {transactions.length === 0 && (
            <tr>
              <td colSpan={renderActions ? 10 : 9} className="px-3 py-8 text-center text-gray-400">
                No transactions match these filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
