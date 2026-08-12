import { apiClient } from '../lib/apiClient'
import type {
  ParsedTransaction,
  ParsedTransactionListResponse,
  TransactionListFilters,
} from '../types/transaction'

export const transactionService = {
  async listForJob(
    jobId: string,
    page = 1,
    pageSize = 50,
    filters: TransactionListFilters = {},
  ): Promise<ParsedTransactionListResponse> {
    const { data } = await apiClient.get<ParsedTransactionListResponse>(
      `/jobs/${jobId}/transactions`,
      { params: { page, page_size: pageSize, ...filters } },
    )
    return data
  },

  async get(transactionId: string): Promise<ParsedTransaction> {
    const { data } = await apiClient.get<ParsedTransaction>(`/transactions/${transactionId}`)
    return data
  },

  async approve(transactionId: string): Promise<ParsedTransaction> {
    const { data } = await apiClient.post<ParsedTransaction>(
      `/transactions/${transactionId}/approve`,
    )
    return data
  },

  async patchLedger(transactionId: string, ledgerId: string): Promise<ParsedTransaction> {
    const { data } = await apiClient.patch<ParsedTransaction>(`/transactions/${transactionId}`, {
      ledger_id: ledgerId,
    })
    return data
  },

  async markDuplicate(
    transactionId: string,
    isDuplicate: boolean,
    duplicateOfTransactionId?: string,
  ): Promise<ParsedTransaction> {
    const { data } = await apiClient.post<ParsedTransaction>(
      `/transactions/${transactionId}/mark-duplicate`,
      { is_duplicate: isDuplicate, duplicate_of_transaction_id: duplicateOfTransactionId ?? null },
    )
    return data
  },
}
