import { apiClient } from '../lib/apiClient'
import type { Ledger, LedgerGroup } from '../types/ledger'

export const ledgerService = {
  async list(q?: string): Promise<Ledger[]> {
    const { data } = await apiClient.get<Ledger[]>('/ledgers', { params: q ? { q } : {} })
    return data
  },

  async listGroups(): Promise<LedgerGroup[]> {
    const { data } = await apiClient.get<LedgerGroup[]>('/groups')
    return data
  },

  async create(name: string, groupId: string): Promise<Ledger> {
    const { data } = await apiClient.post<Ledger>('/ledgers', { name, group_id: groupId })
    return data
  },
}
