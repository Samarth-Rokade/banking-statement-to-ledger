export function formatAmount(value: string | null | undefined): string {
  if (!value) return ''
  const num = Number(value)
  if (num === 0) return ''
  return num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function confidenceColorClass(confidence: number | null): string {
  if (confidence === null) return 'text-gray-400'
  if (confidence >= 90) return 'text-green-700'
  if (confidence >= 60) return 'text-amber-700'
  return 'text-red-700'
}
