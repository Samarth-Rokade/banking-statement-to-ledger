export type JobStatus =
  | 'QUEUED'
  | 'PARSING'
  | 'NORMALIZING'
  | 'MATCHING'
  | 'AI_PREDICTING'
  | 'VALIDATING'
  | 'REVIEW_REQUIRED'
  | 'READY'
  | 'EXPORTED'
  | 'FAILED'

export interface StatusHistoryEntry {
  status: JobStatus
  timestamp: string
}

export interface ProcessingJob {
  id: string
  uploaded_file_id: string
  status: JobStatus
  status_history: StatusHistoryEntry[]
  total_transactions: number
  auto_matched_count: number
  ai_predicted_count: number
  manual_review_count: number
  export_ready_count: number
  error_message: string | null
  created_at: string
}

export interface ProcessingJobListResponse {
  items: ProcessingJob[]
  total: number
  page: number
  page_size: number
}

export interface UploadResponse {
  job_id: string
}

export const TERMINAL_JOB_STATUSES: JobStatus[] = ['READY', 'REVIEW_REQUIRED', 'FAILED', 'EXPORTED']
