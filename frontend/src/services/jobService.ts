import { apiClient } from '../lib/apiClient'
import type { ProcessingJob, ProcessingJobListResponse, UploadResponse } from '../types/job'

export const jobService = {
  async upload(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await apiClient.post<UploadResponse>('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async list(page = 1, pageSize = 20): Promise<ProcessingJobListResponse> {
    const { data } = await apiClient.get<ProcessingJobListResponse>('/jobs', {
      params: { page, page_size: pageSize },
    })
    return data
  },

  async get(jobId: string): Promise<ProcessingJob> {
    const { data } = await apiClient.get<ProcessingJob>(`/jobs/${jobId}`)
    return data
  },
}
