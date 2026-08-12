import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { ledgerService } from '../../services/ledgerService'
import type { SimilarCandidate } from '../../types/transaction'

export default function LedgerTypeahead({
  currentLedgerName,
  similarCandidates,
  onSelect,
  disabled,
}: {
  currentLedgerName: string | null
  similarCandidates?: SimilarCandidate[] | null
  onSelect: (ledgerId: string, ledgerName: string) => void
  disabled?: boolean
}) {
  const [query, setQuery] = useState(currentLedgerName ?? '')
  const [isOpen, setIsOpen] = useState(false)
  const debouncedQuery = useDebouncedValue(query, 250)
  const containerRef = useRef<HTMLDivElement>(null)

  // Adjust state during render (not in an effect) when the parent's ledger
  // selection changes underneath us - see https://react.dev/learn/you-might-not-need-an-effect
  const [syncedLedgerName, setSyncedLedgerName] = useState(currentLedgerName)
  if (currentLedgerName !== syncedLedgerName) {
    setSyncedLedgerName(currentLedgerName)
    setQuery(currentLedgerName ?? '')
  }

  const { data: matches } = useQuery({
    queryKey: ['ledger-search', debouncedQuery],
    queryFn: () => ledgerService.list(debouncedQuery || undefined),
    enabled: isOpen,
    staleTime: 10_000,
  })

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const select = (ledgerId: string, ledgerName: string) => {
    setQuery(ledgerName)
    setIsOpen(false)
    onSelect(ledgerId, ledgerName)
  }

  const showSuggestions = isOpen && query.trim().length === 0 && (similarCandidates?.length ?? 0) > 0

  return (
    <div ref={containerRef} className="relative w-64">
      <input
        type="text"
        value={query}
        disabled={disabled}
        placeholder="Search ledgers…"
        onFocus={() => setIsOpen(true)}
        onChange={(event) => {
          setQuery(event.target.value)
          setIsOpen(true)
        }}
        className="w-full rounded border px-2 py-1 text-sm disabled:opacity-50"
      />
      {isOpen && (
        <div className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded border bg-white shadow-lg">
          {showSuggestions && (
            <div className="border-b px-2 py-1 text-xs font-medium uppercase text-gray-400">
              Suggested matches
            </div>
          )}
          {showSuggestions &&
            similarCandidates!.map((candidate) => (
              <button
                key={candidate.ledger_id}
                type="button"
                onClick={() => select(candidate.ledger_id, candidate.ledger_name)}
                className="flex w-full items-center justify-between px-2 py-1.5 text-left text-sm hover:bg-gray-50"
              >
                <span>{candidate.ledger_name}</span>
                <span className="text-xs text-gray-400">{Math.round(candidate.score * 100)}%</span>
              </button>
            ))}
          {!showSuggestions &&
            matches?.map((ledger) => (
              <button
                key={ledger.id}
                type="button"
                onClick={() => select(ledger.id, ledger.name)}
                className="block w-full px-2 py-1.5 text-left text-sm hover:bg-gray-50"
              >
                {ledger.name}
              </button>
            ))}
          {!showSuggestions && matches?.length === 0 && (
            <p className="px-2 py-2 text-sm text-gray-400">No matching ledgers.</p>
          )}
        </div>
      )}
    </div>
  )
}
