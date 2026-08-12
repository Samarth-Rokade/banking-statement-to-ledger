export type ResolutionSource =
  | 'RULE'
  | 'EXACT_MATCH'
  | 'ALIAS_MATCH'
  | 'SIMILARITY_MATCH'
  | 'AI_PREDICTION'
  | 'MANUAL'
  | 'AI_FAILED'

export interface SimilarCandidate {
  ledger_id: string
  ledger_name: string
  score: number
}

export interface ParsedTransaction {
  id: string
  processing_job_id: string
  row_number: number
  txn_date: string
  original_narration: string
  normalized_narration: string | null
  reference: string | null
  debit: string
  credit: string
  balance: string | null
  transaction_type_tag: string | null
  ledger_id: string | null
  group_id: string | null
  confidence: number | null
  resolution_source: ResolutionSource | null
  similar_candidates: SimilarCandidate[] | null
  requires_review: boolean
  is_duplicate: boolean
  duplicate_of_transaction_id: string | null
  validation_errors: string[] | null
  reviewed_by_user_id: string | null
  reviewed_at: string | null
  voucher_type_id: string | null
}

export interface ParsedTransactionListResponse {
  items: ParsedTransaction[]
  total: number
  page: number
  page_size: number
}

export interface TransactionListFilters {
  requires_review?: boolean
  resolution_source?: ResolutionSource
}
