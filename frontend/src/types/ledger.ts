export type LedgerCreatedVia = 'SEED' | 'RULE' | 'AI' | 'MANUAL'

export interface Ledger {
  id: string
  name: string
  group_id: string
  usage_count: number
  confidence_baseline: number
  created_via: LedgerCreatedVia
}

export interface LedgerGroup {
  id: string
  name: string
  tally_group_type: string
  parent_group_id: string | null
}
