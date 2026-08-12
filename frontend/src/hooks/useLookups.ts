import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { ledgerService } from '../services/ledgerService'

// Ledgers and groups are small, mostly-static reference tables (a few hundred rows
// at most) - fetching the full list once and looking up by id client-side is
// simpler than the backend joining ledger/group names onto every transaction row.
export function useLedgerLookup() {
  const { data: ledgers, isLoading } = useQuery({
    queryKey: ['ledgers'],
    queryFn: () => ledgerService.list(),
    staleTime: 30_000,
  })

  const byId = useMemo(() => {
    const map = new Map<string, string>()
    for (const ledger of ledgers ?? []) map.set(ledger.id, ledger.name)
    return map
  }, [ledgers])

  return { ledgers: ledgers ?? [], ledgerNameById: byId, isLoading }
}

export function useGroupLookup() {
  const { data: groups, isLoading } = useQuery({
    queryKey: ['groups'],
    queryFn: () => ledgerService.listGroups(),
    staleTime: 60_000,
  })

  const byId = useMemo(() => {
    const map = new Map<string, string>()
    for (const group of groups ?? []) map.set(group.id, group.name)
    return map
  }, [groups])

  return { groups: groups ?? [], groupNameById: byId, isLoading }
}
