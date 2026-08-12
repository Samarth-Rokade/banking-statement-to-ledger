import { apiClient } from '../lib/apiClient'

export type ExportFormat = 'csv' | 'excel' | 'xml'

const FILENAME_FALLBACK: Record<ExportFormat, string> = {
  csv: 'export.csv',
  excel: 'export.xlsx',
  xml: 'export.xml',
}

function extractFilename(contentDisposition: string | undefined, fallback: string): string {
  const match = contentDisposition?.match(/filename="?([^"]+)"?/)
  return match?.[1] ?? fallback
}

export const exportService = {
  async download(jobId: string, format: ExportFormat, force: boolean): Promise<void> {
    const response = await apiClient.get(`/export/${jobId}/${format}`, {
      params: { force },
      responseType: 'blob',
    })

    const filename = extractFilename(response.headers['content-disposition'], FILENAME_FALLBACK[format])
    const url = window.URL.createObjectURL(response.data as Blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  },
}
